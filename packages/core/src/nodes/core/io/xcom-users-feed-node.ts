// src/nodes/core/io/xcom-users-feed-node.ts
// Translated from: nodes/core/io/xcom_users_feed_node.py

import { Base } from '../../base/base-node';
import { getVault } from '../../../core/api-key-vault';
import { NodeCategory, ParamMeta, type NodeUIConfig } from '../../../core/types';

/**
 * Represents a post from X.com
 */
export interface XPost {
  id: string;
  text: string;
  author_id: string;
  author_username: string;
  author_name: string;
  created_at: string;
  metrics: Record<string, unknown>;
  media: Array<Record<string, unknown>>;
}

/**
 * Fetches posts from a list of X.com (Twitter) usernames.
 *
 * Requires X API credentials:
 * - XCOM_BEARER_TOKEN: OAuth 2.0 Bearer Token for authentication
 *
 * Input:
 * - text: str - Comma-separated usernames from TextInput node (e.g., "elonmusk, naval, paulg")
 *
 * Output:
 * - posts: list[dict] - List of posts sorted by recency
 * - feed_text: str - Concatenated text of all posts for downstream processing
 * - post_count: int - Total number of posts retrieved
 */
export class XcomUsersFeed extends Base {
  static inputs = { text: String };
  static outputs = { posts: Array, feed_text: String, post_count: Number };
  static required_keys = ['XCOM_BEARER_TOKEN'];

  static uiConfig: NodeUIConfig = {
    size: [280, 140],
    displayResults: false,
    resizable: true,
  };

  static defaultParams = {
    tweets_per_user: 10,
    include_retweets: false,
    include_replies: false,
  };

  static paramsMeta: ParamMeta[] = [
    {
      name: 'tweets_per_user',
      type: 'integer',
      default: 10,
      label: 'Posts Per User',
      description: 'Number of recent posts to fetch per user',
      min: 1,
      max: 100,
    },
    {
      name: 'include_retweets',
      type: 'combo',
      default: false,
      options: [true, false],
      label: 'Include Retweets',
    },
    {
      name: 'include_replies',
      type: 'combo',
      default: false,
      options: [true, false],
      label: 'Include Replies',
    },
  ];

  static CATEGORY = NodeCategory.IO;
  static ui_module = 'XcomUsersFeedNodeUI';

  private static API_BASE = 'https://api.x.com/2';
  private static RATE_LIMIT_DELAY = 1000; // ms

  protected async executeImpl(
    inputs: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const bearerToken = getVault().get('XCOM_BEARER_TOKEN');
    if (!bearerToken) {
      throw new Error('XCOM_BEARER_TOKEN is required but not set in vault');
    }

    const usernames = this.collectUsernames(inputs);

    if (usernames.length === 0) {
      console.warn('XcomUsersFeed: No usernames provided');
      return { posts: [], feed_text: '', post_count: 0 };
    }

    const headers = {
      Authorization: `Bearer ${bearerToken}`,
      'Content-Type': 'application/json',
    };

    this.reportProgress(10.0, `Resolving ${usernames.length} usernames...`);
    const users = await this.resolveUsernames(headers, usernames);

    if (users.length === 0) {
      throw new Error('Could not resolve any usernames. Check they exist.');
    }

    const allPosts: XPost[] = [];
    const totalUsers = users.length;

    for (let idx = 0; idx < users.length; idx++) {
      const user = users[idx];
      if (!user) continue;

      const progress = 15.0 + (idx / totalUsers) * 80.0;
      this.reportProgress(progress, `Fetching posts from @${user.username}...`);

      const posts = await this.getUserTweets(headers, user);
      allPosts.push(...posts);

      // Rate limit delay
      await this.sleep(XcomUsersFeed.RATE_LIMIT_DELAY);
    }

    // Sort by recency
    allPosts.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));

    const postsDicts = allPosts.map((p) => this.postToDict(p));
    const feedText = this.buildFeedText(allPosts);

    this.reportProgress(
      100.0,
      `Completed: ${allPosts.length} posts from ${totalUsers} users`
    );

    return {
      posts: postsDicts,
      feed_text: feedText,
      post_count: allPosts.length,
    };
  }

  private postToDict(post: XPost): Record<string, unknown> {
    return {
      id: post.id,
      text: post.text,
      author_id: post.author_id,
      author_username: post.author_username,
      author_name: post.author_name,
      created_at: post.created_at,
      metrics: post.metrics,
      media: post.media,
    };
  }

  private collectUsernames(inputs: Record<string, unknown>): string[] {
    const usernames: string[] = [];

    const inputText = inputs.text;
    if (inputText && typeof inputText === 'string') {
      const parsed = inputText
        .split(',')
        .map((u) => u.trim().replace(/^@/, ''))
        .filter((u) => u.length > 0);
      usernames.push(...parsed);
    }

    // Deduplicate (case-insensitive)
    const seen = new Set<string>();
    const deduped: string[] = [];
    for (const u of usernames) {
      const lower = u.toLowerCase();
      if (!seen.has(lower)) {
        seen.add(lower);
        deduped.push(u);
      }
    }

    return deduped;
  }

  private async resolveUsernames(
    headers: Record<string, string>,
    usernames: string[]
  ): Promise<Array<{ id: string; username: string; name: string }>> {
    const users: Array<{ id: string; username: string; name: string }> = [];
    const batchSize = 100;

    for (let i = 0; i < usernames.length; i += batchSize) {
      const batch = usernames.slice(i, i + batchSize);
      const params = new URLSearchParams({
        usernames: batch.join(','),
        'user.fields': 'id,name,username,profile_image_url,description',
      });

      try {
        const response = await fetch(
          `${XcomUsersFeed.API_BASE}/users/by?${params.toString()}`,
          { headers }
        );

        if (response.status === 429) {
          throw new Error(
            'X API rate limit exceeded (429). Wait 15 minutes before trying again, ' +
              'or upgrade your API access tier.'
          );
        } else if (response.status === 401) {
          throw new Error(
            'X API authentication failed (401). Check your XCOM_BEARER_TOKEN is valid.'
          );
        } else if (response.status === 403) {
          throw new Error(
            'X API access forbidden (403). Your API tier may not have access to this endpoint.'
          );
        } else if (response.status !== 200) {
          console.warn(`Failed to resolve usernames batch: ${response.status}`);
          continue;
        }

        const data = (await response.json()) as {
          data?: Array<{ id: string; username: string; name: string }>;
          errors?: Array<{ detail?: string }>;
        };

        const results = data.data || [];
        users.push(...results);

        const errors = data.errors || [];
        for (const err of errors) {
          console.warn(`Username resolution error: ${err.detail || JSON.stringify(err)}`);
        }

        if (i + batchSize < usernames.length) {
          await this.sleep(XcomUsersFeed.RATE_LIMIT_DELAY);
        }
      } catch (error) {
        if (error instanceof Error && error.message.includes('rate limit')) {
          throw error;
        }
        console.warn(`Error resolving usernames: ${error}`);
      }
    }

    return users;
  }

  private async getUserTweets(
    headers: Record<string, string>,
    user: { id: string; username: string; name: string }
  ): Promise<XPost[]> {
    const userId = user.id;
    const username = user.username || 'unknown';
    const name = user.name || username;

    const tweetsPerUserRaw = this.params.tweets_per_user;
    let tweetsPerUser = 10;
    if (typeof tweetsPerUserRaw === 'number') {
      tweetsPerUser = tweetsPerUserRaw;
    } else if (typeof tweetsPerUserRaw === 'string' && /^\d+$/.test(tweetsPerUserRaw)) {
      tweetsPerUser = parseInt(tweetsPerUserRaw, 10);
    }

    const includeRetweets = Boolean(this.params.include_retweets);
    const includeReplies = Boolean(this.params.include_replies);

    const excludeTypes: string[] = [];
    if (!includeRetweets) {
      excludeTypes.push('retweets');
    }
    if (!includeReplies) {
      excludeTypes.push('replies');
    }

    const params = new URLSearchParams({
      max_results: String(Math.min(tweetsPerUser, 100)),
      'tweet.fields': 'id,text,created_at,public_metrics,attachments',
      expansions: 'attachments.media_keys',
      'media.fields': 'url,preview_image_url,type',
    });

    if (excludeTypes.length > 0) {
      params.set('exclude', excludeTypes.join(','));
    }

    try {
      const response = await fetch(
        `${XcomUsersFeed.API_BASE}/users/${userId}/tweets?${params.toString()}`,
        { headers }
      );

      if (response.status === 429) {
        console.warn(`Rate limit hit for @${username}, skipping`);
        return [];
      } else if (response.status !== 200) {
        console.warn(`Failed to fetch tweets for @${username}: ${response.status}`);
        return [];
      }

      const data = (await response.json()) as {
        data?: Array<{
          id: string;
          text: string;
          created_at?: string;
          public_metrics?: Record<string, unknown>;
          attachments?: { media_keys?: string[] };
        }>;
        includes?: {
          media?: Array<{ media_key: string; [key: string]: unknown }>;
        };
      };

      const tweetsData = data.data || [];
      const includes = data.includes || {};
      const mediaMap = new Map<string, Record<string, unknown>>();

      for (const m of includes.media || []) {
        mediaMap.set(m.media_key, m);
      }

      const posts: XPost[] = [];

      for (const tweet of tweetsData) {
        const media: Array<Record<string, unknown>> = [];

        if (tweet.attachments) {
          const mediaKeys = tweet.attachments.media_keys || [];
          for (const key of mediaKeys) {
            const mediaItem = mediaMap.get(key);
            if (mediaItem) {
              media.push(mediaItem);
            }
          }
        }

        posts.push({
          id: tweet.id,
          text: tweet.text,
          author_id: userId,
          author_username: username,
          author_name: name,
          created_at: tweet.created_at || '',
          metrics: tweet.public_metrics || {},
          media,
        });
      }

      return posts;
    } catch (error) {
      console.warn(`Error fetching tweets for @${username}: ${error}`);
      return [];
    }
  }

  private buildFeedText(posts: XPost[]): string {
    const lines: string[] = [];

    for (const post of posts) {
      const timestamp = post.created_at ? post.created_at.slice(0, 10) : 'Unknown';
      lines.push(`[@${post.author_username}] (${timestamp}): ${post.text}`);
      lines.push('');
    }

    return lines.join('\n');
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
