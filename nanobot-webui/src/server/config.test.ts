import { describe, expect, it } from 'vitest'
import { loadConfig, publicInstance, websocketUrlForInstance, type NanobotInstance } from './config'

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
    expect(config.dataDir).toBe('/data')
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

  it('rejects instance env vars without a config file', () => {
    expect(() => loadConfig({
      AUTH_TOKEN: 'dashboard',
      NANOBOT_INSTANCES: 'alpha=http://one',
      NANOBOT_INSTANCE_TOKENS: 'alpha=a-admin-token',
      NANOBOT_INSTANCE_WEBSOCKET_TOKENS: 'alpha=a-ws-token'
    })).toThrow(/WEBUI_CONFIG is required/)
  })

  it('rejects duplicate instance ids', () => {
    expect(() => loadConfig({
      WEBUI_CONFIG_JSON: JSON.stringify({
        authToken: 'file-dashboard',
        instances: [
          {
            id: 'alpha',
            adminBaseUrl: 'http://one',
            adminToken: 'alpha-admin-token',
            websocketUrl: 'ws://one:8765/',
            websocketToken: 'alpha-ws-token'
          },
          {
            id: 'alpha',
            adminBaseUrl: 'http://two',
            adminToken: 'alpha-admin-token',
            websocketUrl: 'ws://two:8765/',
            websocketToken: 'alpha-ws-token'
          }
        ]
      })
    })).toThrow(/duplicate instance id/)
  })
})

describe('websocketUrlForInstance', () => {
  const baseInstance: NanobotInstance = {
    id: 'alpha',
    name: 'Alpha',
    baseUrl: 'http://nanobot-alpha:18790',
    adminToken: 'admin-secret',
    websocketToken: 'ws-secret',
    enabled: true
  }

  it('derives websocket url from configured instance websocket token only', () => {
    expect(websocketUrlForInstance(baseInstance)).toBe('ws://nanobot-alpha:8765/?client_id=nanobot-webui&token=ws-secret')
  })

  it('adds token and client id to an explicit websocket url', () => {
    expect(websocketUrlForInstance({ ...baseInstance, websocketUrl: 'ws://nanobot-alpha:8765/' })).toBe(
      'ws://nanobot-alpha:8765/?client_id=nanobot-webui&token=ws-secret'
    )
  })

  it('preserves non-sensitive query params and overrides token/client_id', () => {
    expect(
      websocketUrlForInstance({
        ...baseInstance,
        websocketUrl: 'ws://nanobot-alpha:8765/ws?room=ops&token=wrong&client_id=browser'
      })
    ).toBe('ws://nanobot-alpha:8765/ws?room=ops&token=ws-secret&client_id=nanobot-webui')
  })
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
