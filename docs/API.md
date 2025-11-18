# Fig-Node API Documentation

## Overview

The Fig-Node API provides a RESTful HTTP API and WebSocket protocol for executing agentic finance and trading workflows.

## Base URL

```
http://localhost:8000
```

## OpenAPI Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Versioning

All API endpoints are versioned under `/api/v1`:

```
/api/v1/nodes
/api/v1/api_keys
```

## HTTP Endpoints

### Get Node Metadata

```http
GET /api/v1/nodes
```

Returns metadata for all registered nodes including inputs, outputs, parameters, categories, and required API keys.

**Response:**
```json
{
  "nodes": {
    "NodeName": {
      "inputs": {...},
      "outputs": {...},
      "params": [...],
      "category": "category_name",
      "required_keys": ["API_KEY_NAME"],
      "description": "Node description"
    }
  }
}
```

### Get API Keys

```http
GET /api/v1/api_keys
```

Returns all stored API keys.

**Response:**
```json
{
  "keys": {
    "POLYGON_API_KEY": "value",
    "TAVILY_API_KEY": "value"
  }
}
```

### Set API Key

```http
POST /api/v1/api_keys
Content-Type: application/json

{
  "key_name": "POLYGON_API_KEY",
  "value": "your-api-key-value"
}
```

**Response:**
```json
{
  "status": "success"
}
```

### Delete API Key

```http
DELETE /api/v1/api_keys
Content-Type: application/json

{
  "key_name": "POLYGON_API_KEY"
}
```

**Response:**
```json
{
  "status": "success"
}
```

## Error Responses

All endpoints return standardized error responses:

### Validation Error (422)

```json
{
  "error": "Validation error",
  "details": [
    {
      "loc": ["field_name"],
      "msg": "error message",
      "type": "error_type"
    }
  ]
}
```

### Internal Server Error (500)

```json
{
  "error": "Internal server error",
  "message": "Error description"
}
```

## WebSocket Protocol

See [WEBSOCKET_PROTOCOL.md](./WEBSOCKET_PROTOCOL.md) for detailed WebSocket documentation.

## Authentication

Currently, the API does not require authentication for local development. API keys are stored locally in the `.env` file.

## Rate Limiting

No rate limiting is currently implemented.

## Schema Validation

All requests are validated using Pydantic models. Invalid requests will return a 422 status code with detailed validation errors.

## TypeScript Type Generation

Generate TypeScript types from the OpenAPI spec:

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o types/api.ts
```

