import { describe, expect, it } from 'vitest'
import { loadConfig, publicInstance, websocketUrlForInstance } from './config'

describe('loadConfig', () => {
  it('loads dashboard auth and instances from a mounted config file', () => {
    const config = loadConfig({
      PORT: '6061',
      WEBUI_CONFIG_JSON: JSON.stringify({
        authToken: 'file-dashboard',
        instances: [
          {
            id: 'alpha',
            name: 'Alpha Bot',
            adminBaseUrl: 'http://nanobot-alpha:18790/',
            adminToken: 'alpha-admin-token',
            websocketUrl: 'ws://nanobot-alpha:9876/chat',
            websocketToken: 'alpha-ws-token',
            enabled: false
          }
        ]
      })
    })

    expect(config.port).toBe(6061)
    expect(config.authToken).toBe('file-dashboard')
    expect(config.instances).toEqual([
      {
        id: 'alpha',
        name: 'Alpha Bot',
        baseUrl: 'http://nanobot-alpha:18790',
        adminToken: 'alpha-admin-token',
        websocketUrl: 'ws://nanobot-alpha:9876/chat',
        websocketToken: 'alpha-ws-token',
        enabled: false
      }
    ])
  })

  it('lets AUTH_TOKEN override auth token from config file', () => {
    const config = loadConfig({
      AUTH_TOKEN: 'env-dashboard',
      WEBUI_CONFIG_JSON: JSON.stringify({
        authToken: 'file-dashboard',
        instances: [
          {
            id: 'alpha',
            adminBaseUrl: 'http://nanobot-alpha:18790',
            adminToken: 'alpha-admin-token',
            websocketUrl: 'ws://nanobot-alpha:8765/',
            websocketToken: 'alpha-ws-token'
          }
        ]
      })
    })

    expect(config.authToken).toBe('env-dashboard')
  })

  it('rejects config file instances without websocket url', () => {
    expect(() => loadConfig({
      WEBUI_CONFIG_JSON: JSON.stringify({
        authToken: 'file-dashboard',
        instances: [
          {
            id: 'alpha',
            adminBaseUrl: 'http://nanobot-alpha:18790',
            adminToken: 'alpha-admin-token',
            websocketToken: 'alpha-ws-token'
          }
        ]
      })
    })).toThrow(/websocketUrl is required for instance: alpha/)
  })

  it('parses static instances and keeps tokens server-side', () => {
    const config = loadConfig({
      PORT: '6060',
      AUTH_TOKEN: 'dashboard',
      NANOBOT_INSTANCES: 'alpha=http://nanobot-alpha:18790,beta=http://nanobot-beta:18790',
      NANOBOT_INSTANCE_TOKENS: 'alpha=a-admin-token,beta=b-admin-token',
      NANOBOT_INSTANCE_WEBSOCKET_TOKENS: 'alpha=a-ws-token,beta=b-ws-token'
    })

    expect(config.port).toBe(6060)
    expect(config.authToken).toBe('dashboard')
    expect(config.instances.map((i) => i.id)).toEqual(['alpha', 'beta'])
    expect(config.instances[0].adminToken).toBe('a-admin-token')
    expect(config.instances[0].websocketToken).toBe('a-ws-token')
  })

  it('rejects missing websocket tokens', () => {
    expect(() => loadConfig({
      AUTH_TOKEN: 'dashboard',
      NANOBOT_INSTANCES: 'alpha=http://one',
      NANOBOT_INSTANCE_TOKENS: 'alpha=a-admin-token'
    })).toThrow(/missing websocket token for instance: alpha/)
  })

  it('rejects duplicate instance ids', () => {
    expect(() => loadConfig({
      AUTH_TOKEN: 'dashboard',
      NANOBOT_INSTANCES: 'alpha=http://one,alpha=http://two',
      NANOBOT_INSTANCE_TOKENS: 'alpha=a-token',
      NANOBOT_INSTANCE_WEBSOCKET_TOKENS: 'alpha=a-ws-token'
    })).toThrow(/duplicate instance id/)
  })
})

it('derives websocket url from configured instance websocket token only', () => {
  expect(websocketUrlForInstance({
    id: 'alpha',
    name: 'alpha',
    baseUrl: 'http://nanobot-alpha:18790',
    adminToken: 'admin-secret',
    websocketToken: 'ws-secret',
    enabled: true
  })).toBe('ws://nanobot-alpha:8765/?client_id=nanobot-webui&token=ws-secret')
})

it('returns explicit websocket url overrides as-is', () => {
  expect(websocketUrlForInstance({
    id: 'alpha',
    name: 'alpha',
    baseUrl: 'http://nanobot-alpha:18790',
    adminToken: 'admin-secret',
    websocketToken: 'ws-secret',
    websocketUrl: 'ws://custom.example/chat?token=custom',
    enabled: true
  })).toBe('ws://custom.example/chat?token=custom')
})

it('redacts websocket token and websocket url from public instances', () => {
  expect(publicInstance({
    id: 'alpha',
    name: 'alpha',
    baseUrl: 'http://nanobot-alpha:18790',
    adminToken: 'admin-secret',
    websocketToken: 'ws-secret',
    websocketUrl: 'ws://custom.example/chat?token=custom',
    enabled: true
  })).toEqual({ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true })
})
