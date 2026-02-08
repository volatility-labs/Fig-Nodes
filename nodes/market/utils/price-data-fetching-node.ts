// src/nodes/core/market/utils/price-data-fetching-node.ts

import * as fs from 'fs';
import * as path from 'path';
import { Node, NodeCategory, port, type NodeDefinition } from '@sosa/core';
import type { OHLCVBar } from '../types';

/**
 * Extracts the most recent closing prices from an OHLCV bundle and saves to CSV.
 *
 * This node takes an OHLCV bundle (filtered symbols) as input, displays formatted output,
 * and automatically saves results to a CSV file organized by scan name.
 *
 * Perfect for logging current prices and easy viewing in Excel/Cursor.
 */
export class PriceDataFetching extends Node {
  static definition: NodeDefinition = {
    inputs: { ohlcv_bundle: port('OHLCVBundle') },
    outputs: {
      formatted_output: port('string'),
      csv_file: port('string'),
    },
    category: NodeCategory.MARKET,
    ui: {},
    params: [
      {
        name: 'scan_name',
        type: 'text',
        default: 'default_scan',
        label: 'Scanner Name',
        description:
          "Name for this scanner (e.g., 'momentum_scanner', 'breakout_scanner'). Used to organize CSV files.",
      },
      {
        name: 'save_to_csv',
        type: 'combo',
        default: true,
        options: [true, false],
        label: 'Save to CSV',
        description:
          'Whether to save results to CSV file. Files are saved to results/ folder and easy to open in Excel or Cursor.',
      },
    ],
  };

  protected async run(
    inputs: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const ohlcvBundle =
      (inputs.ohlcv_bundle as Map<string, OHLCVBar[]>) ||
      new Map<string, OHLCVBar[]>();

    console.log(
      `PriceDataFetching node received bundle with ${ohlcvBundle.size} symbols`
    );

    if (ohlcvBundle.size === 0) {
      console.warn('PriceDataFetching node received empty OHLCV bundle');
      return {
        formatted_output:
          'Warning: No price data available - check if OHLCV bundle is connected',
        csv_file: '',
      };
    }

    const scanName =
      typeof this.params.scan_name === 'string'
        ? this.params.scan_name
        : 'default_scan';
    const saveToCsv = this.params.save_to_csv !== false;

    const currentTimeMs = Date.now();
    const currentDatetime = new Date();

    const outputLines: string[] = [];
    outputLines.push(
      `=== ${scanName} - Price Data for ${ohlcvBundle.size} Symbols ===\n`
    );

    // Collect results for CSV
    interface CsvRow {
      symbol: string;
      price: number;
      bar_timestamp: string;
      age_minutes: number;
      open: number | string;
      high: number | string;
      low: number | string;
      volume: number | string;
    }

    const csvRows: CsvRow[] = [];

    for (const [symbolKey, ohlcvData] of ohlcvBundle.entries()) {
      if (!ohlcvData || ohlcvData.length === 0) {
        console.warn(
          `PriceDataFetching node received invalid OHLCV data for ${symbolKey}`
        );
        continue;
      }

      // Get the most recent bar (last in the list)
      const latestBar = ohlcvData[ohlcvData.length - 1];
      if (!latestBar) continue;

      // Extract price
      const priceRaw = latestBar.close ?? 0;
      const price = typeof priceRaw === 'number' ? priceRaw : 0;

      // Calculate delay in minutes
      const barTimestampMs = latestBar.timestamp ?? 0;
      const delayMs = currentTimeMs - barTimestampMs;
      const delayMinutes = delayMs / (1000 * 60);

      // Format timestamp
      const barDatetime = new Date(barTimestampMs);
      const timestampStr = barDatetime.toISOString().slice(0, 19).replace('T', ' ');

      // Format delay for readability
      let ageStr: string;
      if (delayMinutes < 60) {
        ageStr = `${delayMinutes.toFixed(1)} min`;
      } else if (delayMinutes < 1440) {
        ageStr = `${(delayMinutes / 60).toFixed(1)} hrs`;
      } else {
        ageStr = `${(delayMinutes / 1440).toFixed(1)} days`;
      }

      // Create formatted line: SYMBOL: $PRICE @ TIMESTAMP (age)
      outputLines.push(
        `${symbolKey.padEnd(15)} $${price.toFixed(4).padStart(10)}  @  ${timestampStr}  (${ageStr} old)`
      );

      // Collect for CSV
      csvRows.push({
        symbol: symbolKey,
        price: price,
        bar_timestamp: timestampStr,
        age_minutes: Math.round(delayMinutes * 100) / 100,
        open: latestBar.open ?? '',
        high: latestBar.high ?? '',
        low: latestBar.low ?? '',
        volume: latestBar.volume ?? '',
      });
    }

    let formattedOutput = outputLines.join('\n');
    let csvFile = '';

    // Save to CSV if enabled
    if (saveToCsv && csvRows.length > 0) {
      try {
        // Create output directory if it doesn't exist
        const outputDir = path.resolve(process.cwd(), 'output');
        if (!fs.existsSync(outputDir)) {
          fs.mkdirSync(outputDir, { recursive: true });
        }

        // Generate filename: scan_name_YYYYMMDD_HHMMSS.csv
        const dateStr = currentDatetime
          .toISOString()
          .slice(0, 19)
          .replace(/[-:T]/g, '')
          .replace(/(\d{8})(\d{6})/, '$1_$2');
        const filename = `${scanName}_${dateStr}.csv`;
        const csvPath = path.join(outputDir, filename);

        // Write CSV file
        const fieldnames = [
          'symbol',
          'price',
          'bar_timestamp',
          'age_minutes',
          'open',
          'high',
          'low',
          'volume',
        ];

        const csvContent = [
          fieldnames.join(','),
          ...csvRows.map((row) =>
            fieldnames
              .map((field) => {
                const value = row[field as keyof CsvRow];
                // Escape commas and quotes in string values
                if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
                  return `"${value.replace(/"/g, '""')}"`;
                }
                return String(value);
              })
              .join(',')
          ),
        ].join('\n');

        fs.writeFileSync(csvPath, csvContent, 'utf8');

        csvFile = csvPath;
        outputLines.push(`\nSaved to CSV: output/${filename}`);
        formattedOutput = outputLines.join('\n');
        console.log(`PriceDataFetching saved scan '${scanName}' to ${csvPath}`);
      } catch (error) {
        console.error(`Failed to save to CSV: ${error}`);
        outputLines.push(`\nWarning: CSV save failed: ${error}`);
        formattedOutput = outputLines.join('\n');
      }
    }

    console.log(
      `PriceDataFetching node extracted prices for ${ohlcvBundle.size} symbols`
    );

    return {
      formatted_output: formattedOutput,
      csv_file: csvFile,
    };
  }
}
