# Changelog

## v0.2.0 — Non-blocking outbound queue & backorder hold

- Split outbound requests with no available shelf stock into
  `waiting_outbound_orders`, preventing missing items from blocking ready
  requests.
- Automatically promote waiting requests when matching inbound containers are
  stored and become available.

## v0.1.0 — Pre-version baseline

- 2D top-down Pygame grid map with six uniform robots.
- Master AI task coordinator and basic A* pathfinding.
- HUD controls for inbound and outbound orders.
- Initial bottleneck observation: head-on aisle deadlocks.

## Next Planned Milestones

- **v0.3.0:** Multi-agent deadlock and collision resolution with a reservation
  table.
- **v0.4.0:** Gymnasium reinforcement-learning wrapper and policy training.
