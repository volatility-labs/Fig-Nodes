/**
 * Read-only interface for accessing credentials (API keys, tokens, etc.).
 * Core nodes use this interface; concrete implementations live in the server layer.
 */
export interface CredentialProvider {
    get(key: string): string | undefined;
    has(key: string): boolean;
}
/**
 * Key used to inject the CredentialProvider into graphContext.
 */
export declare const CREDENTIAL_PROVIDER_KEY = "__credentialProvider__";
