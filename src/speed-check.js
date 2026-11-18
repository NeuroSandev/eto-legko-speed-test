#!/usr/bin/env node

import { performance } from 'node:perf_hooks';
import { request as httpRequest } from 'node:http';
import { request as httpsRequest } from 'node:https';

const REQUEST_COUNT = 10;

function formatBytes(bytes) {
  const units = ['B', 'KiB', 'MiB', 'GiB'];
  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(2)} ${units[unitIndex]}`;
}

function downloadOnce(inputUrl, redirectsLeft = 5) {
  return new Promise((resolve, reject) => {
    let parsedUrl;
    try {
      parsedUrl = new URL(inputUrl);
    } catch {
      reject(new Error(`Invalid URL: ${inputUrl}`));
      return;
    }

    const requester = parsedUrl.protocol === 'https:' ? httpsRequest : httpRequest;

    const startedAt = performance.now();
    const req = requester(parsedUrl, { method: 'GET' }, (res) => {
      const statusCode = res.statusCode ?? 0;

      if (statusCode >= 300 && statusCode < 400 && res.headers.location) {
        if (redirectsLeft <= 0) {
          reject(new Error('Too many redirects'));
          res.resume();
          return;
        }

        const redirectUrl = new URL(res.headers.location, parsedUrl).toString();
        res.resume();
        downloadOnce(redirectUrl, redirectsLeft - 1)
          .then(resolve)
          .catch(reject);
        return;
      }

      if (statusCode < 200 || statusCode >= 300) {
        reject(new Error(`Request failed with status ${statusCode}`));
        res.resume();
        return;
      }

      let bytes = 0;
      res.on('data', (chunk) => {
        bytes += chunk.length;
      });

      res.on('end', () => {
        const elapsedMs = performance.now() - startedAt;
        resolve({ elapsedMs, bytes });
      });

      res.on('error', (error) => {
        reject(error);
      });
    });

    req.setTimeout(30000, () => {
      req.destroy(new Error('Request timeout (30s)'));
    });

    req.on('error', (error) => {
      reject(error);
    });

    req.end();
  });
}

async function main() {
  const inputUrl = process.argv[2];

  if (!inputUrl) {
    console.error('Usage: npm start -- <URL>');
    process.exit(1);
  }

  const attempts = [];

  for (let index = 1; index <= REQUEST_COUNT; index += 1) {
    const result = await downloadOnce(inputUrl);
    attempts.push(result);
    console.log(`#${index}: ${result.elapsedMs.toFixed(2)} ms, ${formatBytes(result.bytes)}`);
  }

  const totalTimeMs = attempts.reduce((sum, item) => sum + item.elapsedMs, 0);
  const totalBytes = attempts.reduce((sum, item) => sum + item.bytes, 0);
  const averageMs = totalTimeMs / REQUEST_COUNT;

  const seconds = totalTimeMs / 1000;
  const bytesPerSecond = totalBytes / seconds;
  const mibPerSecond = bytesPerSecond / (1024 * 1024);
  const megabitsPerSecond = (bytesPerSecond * 8) / 1_000_000;

  console.log('\nSummary');
  console.log(`Requests: ${REQUEST_COUNT}`);
  console.log(`Average time: ${averageMs.toFixed(2)} ms`);
  console.log(`Total downloaded: ${formatBytes(totalBytes)} (${totalBytes} B)`);
  console.log(`Download speed: ${mibPerSecond.toFixed(3)} MiB/s`);
  console.log(`Download speed: ${megabitsPerSecond.toFixed(3)} Mbit/s`);
}

main().catch((error) => {
  console.error(`Error: ${error.message}`);
  process.exit(1);
});
