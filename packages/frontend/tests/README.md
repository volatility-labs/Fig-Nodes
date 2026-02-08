# Test Structure

This directory contains the refactored test suite for the sosa UI application.

## Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── services/           # Service unit tests
│   │   ├── AppState.test.ts
│   │   ├── APIKeyManager.test.ts
│   │   ├── DialogManager.test.ts
│   │   ├── FileManager.test.ts
│   │   ├── LinkModeManager.test.ts
│   │   ├── UIModuleLoader.test.ts
│   │   └── EditorInitializer.test.ts
│   ├── nodes.test.ts       # Node UI unit tests
│   └── types.test.ts       # Type utility unit tests
├── integration/            # Integration tests
│   ├── app-integration.test.ts
│   ├── services-integration.test.ts
│   ├── node-ui-integration.test.ts
│   └── app.test.ts         # Legacy app tests (refactored)
├── setup.ts               # Test setup and mocks
├── vitest.config.ts       # Vitest configuration
└── README.md              # This file
```

## Test Categories

### Unit Tests
- **Services**: Test individual service classes in isolation
- **Nodes**: Test node UI classes and their behavior
- **Types**: Test type utility functions

### Integration Tests
- **App Integration**: Test complete app initialization and flows
- **Services Integration**: Test service interactions
- **Node UI Integration**: Test node interactions and workflows

## Running Tests

```bash
# Run all tests
npm test

# Run unit tests only
npm run test:unit

# Run integration tests only
npm run test:integration

# Run with coverage
npm run test:coverage

# Run specific test file
npm test -- tests/unit/services/AppState.test.ts
```

## Test Guidelines

### Unit Tests
- Test individual components in isolation
- Mock all external dependencies
- Focus on specific functionality
- Should be fast and deterministic

### Integration Tests
- Test component interactions
- Use real DOM environment
- Test complete workflows
- May be slower but test real behavior

### Mocking Strategy
- Mock external APIs (fetch, WebSocket)
- Mock DOM operations where needed
- Use JSDOM for DOM testing
- Mock localStorage and other browser APIs

## Key Testing Areas

1. **Service Layer**: AppState, APIKeyManager, FileManager, etc.
2. **Node UI**: Custom node implementations and rendering
3. **App Initialization**: Complete app startup and configuration
4. **File Operations**: Save, load, autosave functionality
5. **User Interactions**: Button clicks, form submissions, etc.
6. **Error Handling**: Graceful failure and recovery
7. **State Management**: Data persistence and restoration

## Coverage Goals

- **Unit Tests**: 90%+ coverage for services and utilities
- **Integration Tests**: Cover major user workflows
- **Critical Paths**: 100% coverage for core functionality

## Debugging Tests

```bash
# Run tests in watch mode
npm run test:watch

# Run tests with verbose output
npm test -- --reporter=verbose

# Debug specific test
npm test -- --run tests/unit/services/AppState.test.ts
```
