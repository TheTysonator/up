# Hermes Agent Website Monitor Plugin 🌐⏱️

An open-source plugin for the [Hermes Agent](https://github.com/NousResearch/hermes-agent) framework. It runs a silent, asynchronous background thread that pings your websites every 60 seconds and instantly sends Matrix, Telegram, or Discord alerts the moment a site goes down or recovers.

It also registers three custom tools so that your Hermes Agent can dynamically manage the monitor list when you ask it to in chat.

## Features

* 🚀 **Silent Background Polling:** Pings monitored URLs every 60 seconds via lightweight HTTP GET requests.
* 🔔 **Transition-Based Alerting:** Only sends alerts on state transitions (UP ➡️ DOWN or DOWN ➡️ UP). It remains dead silent otherwise to avoid spamming your chats.
* 🤖 **Agent Tools:** Provides `add_monitor`, `remove_monitor`, and `list_monitors` tools directly to the agent.
* ⚙️ **Uptime State Persistence:** Saves states to `~/.hermes/website_monitors.json` so states survive system restarts.

---

## Installation

Run this slash command directly in your Hermes Matrix, Telegram, or Discord chat:

