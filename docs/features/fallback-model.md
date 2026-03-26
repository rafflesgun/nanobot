# Fallback Model Feature

The fallback model feature provides automatic failover capability when the primary model becomes unavailable or hits usage limits.

## Overview

The fallback model system monitors for various failure conditions and automatically switches to a backup model when the primary model fails. This ensures continuous operation even when facing:

- Model unavailability (404 errors)
- Rate limiting and quota exhaustion (403 errors)
- Server errors (502, 503)
- Network timeouts
- Invalid model specifications

## Configuration

Configure the fallback model in your nanobot configuration:

```yaml
# config.yaml
llm:
  model: "primary-model-name"  # Main model to use
  fallback_model: "backup-model-name"  # Fallback when primary fails
```

Or via environment variables:

```bash
export NANOBOT_FALLBACK_MODEL="gpt-4-turbo-preview"
```

## Supported Failure Conditions

The system automatically detects and handles these failure types:

- **404 errors**: Model not found or unavailable
- **403 errors**: Quota exhaustion (free tier limits, rate limits)
- **502/503 errors**: Service temporarily unavailable
- **Timeout errors**: Network or server delays
- **Provider errors**: General upstream failures
- **Invalid model errors**: Incorrect model specifications

## How It Works

1. **Primary Attempt**: Requests are first sent to the configured primary model
2. **Failure Detection**: If the primary model fails with a recognized error condition
3. **Fallback Activation**: The system automatically retries with the fallback model
4. **Error Propagation**: If both models fail, the original error is raised

## Usage Scenarios

### Continuous Operation
Ensures your bot continues operating even when premium models hit daily limits.

### Cost Management
Can be configured to fall back from expensive models to more economical alternatives when quotas are exceeded.

### Reliability
Provides resilience against temporary service disruptions or model unavailability.

## Monitoring

Fallback events are logged as warnings to help monitor usage patterns:

```
WARNING - Primary model failed, trying fallback model: gpt-4-turbo-preview
```

## Best Practices

- Choose a fallback model that's reliably available
- Consider cost implications when selecting fallback models
- Monitor fallback usage to optimize your configuration
- Test the fallback mechanism periodically to ensure it works as expected