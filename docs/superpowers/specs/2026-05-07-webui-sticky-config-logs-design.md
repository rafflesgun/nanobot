# WebUI Sticky Config Logs Design

## Goal

Adopt the layout behavior inspired by `Cli-Proxy-API-Management-Center`: fixed floating header controls, glass sidebar panel, top-aligned scrollable content, aligned toolbar actions, split settings/config panels, editor/form/raw modes, log filtering/raw modes, and visible webui runtime logs.

## Layout

- The authenticated shell uses a full-height viewport with no vertical centering.
- Sidebar is a glass panel with stable width, top/bottom gutter, and internal navigation.
- Header controls float above the content and do not move when switching primary pages.
- Content starts from a consistent top offset and scrolls inside the content region.
- Primary pages and Manage subpages keep their first panel aligned to the top.

## Settings Editor

Settings supports mode tabs:

- `GUI Form`: existing model/provider form.
- `JSON`: editable JSON payload for agent settings.
- `Markdown`: generated markdown summary for review/copying.

The Save action is aligned in a toolbar and applies the current GUI/JSON state. Invalid JSON is shown as an inline error and does not call the API.

## Logs Viewer

Logs supports:

- instance selector and log selector.
- filter input for visible lines.
- `Formatted` and `Raw` view toggle.
- aligned toolbar actions.

## WebUI Runtime Logs

The webui records lightweight runtime log lines in memory for dashboard operations: startup/app creation, authenticated API requests, denied auth, and state saves. A protected `/api/webui/logs` endpoint returns recent lines, and the Manage Logs panel can display a WebUI Runtime source in addition to nanobot instance logs.

## Testing

- Component tests assert shell structure/class hooks and no content-centering class.
- Settings tests cover GUI/JSON/Markdown modes and invalid JSON handling.
- Logs tests cover filter/raw mode behavior.
- Server tests cover webui runtime log endpoint and auth protection.
