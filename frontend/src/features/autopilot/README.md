# Autopilot frontend feature

`AutopilotDashboard.tsx` is a standalone, dependency-injected feature component. Provide an `AutopilotApi` adapter from the authenticated shared API client. It intentionally does not register routes, create a second app, initiate background polling, or claim integrations succeeded without server responses. Import `autopilot.css` from the host app after verifying its design tokens. The component requires React and uses native accessible controls.
