---
id: api-rate-limits
title: API rate limits
plan_specific: true
keywords: api rate limit requests per minute 429 throttled quota
---
# API rate limits

Requests above the limit return HTTP 429 with a Retry-After header.

## Free

On the Free plan the API allows 60 requests per minute per workspace.

## Pro

On the Pro plan the API allows 600 requests per minute per workspace.

## Business

On the Business plan the API allows 3,000 requests per minute per workspace, and higher limits can be requested.
