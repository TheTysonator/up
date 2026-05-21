/**
 * Website Monitor Dashboard Tab
 * Plain IIFE using globals from window.__HERMES_PLUGIN_SDK__
 */
(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  const { React } = SDK;
  const { Card, CardHeader, CardTitle, CardContent, Badge, Button } = SDK.components;
  const { useState, useEffect } = SDK.hooks;

  function WebsiteMonitorPage() {
    const [monitors, setMonitors] = useState({});
    const [newUrl, setNewUrl] = useState("");
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState(null);

    function fetchStatus() {
      setLoading(true);

      SDK.fetchJSON("/api/plugins/uptime/status")
        .then(function (data) {
          if (data && data.success) {
            setMonitors(data.monitors || {});
          } else {
            setMessage("Failed to load: backend returned unsuccessful response.");
          }
        })
        .catch(function (err) {
          const errMsg = err ? (err.message || String(err)) : "Unknown Exception";
          setMessage("Failed to load monitors: " + errMsg);
          console.error("Website Monitor load error:", err);
        })
        .finally(function () {
          setLoading(false);
        });
    }

    useEffect(function () {
      fetchStatus();
      const interval = setInterval(fetchStatus, 15000);
      return function () {
        clearInterval(interval);
      };
    }, []);

    function handleAdd(e) {
      e.preventDefault();
      if (!newUrl.trim()) return;

      setLoading(true);

      SDK.fetchJSON("/api/plugins/uptime/add?url=" + encodeURIComponent(newUrl))
        .then(function (data) {
          if (data && data.success) {
            setMessage("Successfully added " + newUrl);
            setNewUrl("");
            fetchStatus();
          } else {
            setMessage("Error: " + (data ? data.error : "Unknown Error"));
          }
        })
        .catch(function (err) {
          setMessage("API request failed: " + (err ? err.message : String(err)));
        })
        .finally(function () {
          setLoading(false);
        });
    }

    function handleRemove(url) {
      if (!confirm("Are you sure you want to stop monitoring " + url + "?")) return;

      setLoading(true);

      SDK.fetchJSON("/api/plugins/uptime/remove?url=" + encodeURIComponent(url))
        .then(function (data) {
          if (data && data.success) {
            setMessage("Removed " + url);
            fetchStatus();
          } else {
            setMessage("Error: " + (data ? data.error : "Unknown Error"));
          }
        })
        .catch(function (err) {
          setMessage("API request failed: " + (err ? err.message : String(err)));
        })
        .finally(function () {
          setLoading(false);
        });
    }

    const monitorsSafe = monitors || {};

    const groupedMonitors = Object.keys(monitorsSafe).reduce(function (groups, url) {
      const monitorInfo = monitorsSafe[url] || {};
      const appName = monitorInfo.app || "Unassigned";

      if (!groups[appName]) {
        groups[appName] = [];
      }

      groups[appName].push(url);
      return groups;
    }, {});

    const appNames = Object.keys(groupedMonitors).sort();

    return React.createElement("div", { className: "flex flex-col gap-6 p-4" },

      React.createElement(Card, null,
        React.createElement(CardHeader, null,
          React.createElement("div", { className: "flex items-center justify-between" },
            React.createElement(CardTitle, { className: "text-xl font-bold" }, "🌐 Website Uptime Monitor"),
            React.createElement(Button, {
              onClick: fetchStatus,
              disabled: loading,
              className: "text-xs border border-border px-3 py-1 cursor-pointer"
            }, loading ? "Refreshing..." : "↻ Refresh")
          )
        ),

        React.createElement(CardContent, { className: "flex flex-col gap-4" },
          React.createElement("p", { className: "text-sm text-muted-foreground" },
            "Add and manage URLs for real-time uptime checks. Background checks occur silently every 60 seconds."
          ),

          React.createElement("form", { onSubmit: handleAdd, className: "flex items-center gap-3 mt-2" },
            React.createElement("input", {
              type: "text",
              placeholder: "https://mywebsite.com",
              value: newUrl,
              onChange: function (e) {
                setNewUrl(e.target.value);
              },
              disabled: loading,
              className: "flex-1 border border-border rounded-md px-3 py-2 text-sm bg-background/50 h-9 outline-none focus:ring-1 focus:ring-ring"
            }),

            React.createElement(Button, {
              type: "submit",
              disabled: loading || !newUrl.trim(),
              className: "bg-primary text-primary-foreground font-semibold px-4 py-2 hover:bg-primary/90 text-sm cursor-pointer"
            }, "＋ Add Monitor")
          ),

          message && React.createElement("div", {
            className: "text-xs font-mono text-amber-500 mt-1"
          }, message)
        )
      ),

      React.createElement(Card, null,
        React.createElement(CardHeader, null,
          React.createElement(CardTitle, { className: "text-base font-semibold" }, "📺 Live Monitor Statuses")
        ),

        React.createElement(CardContent, null,
          appNames.length === 0 ?
            React.createElement("div", {
              className: "text-sm text-muted-foreground text-center py-6 border border-dashed border-border"
            }, "No websites are currently being monitored. Add one above to get started!")
            :
            React.createElement("div", { className: "flex flex-col gap-6" },
              appNames.map(function (appName) {
                const urls = groupedMonitors[appName] || [];

                return React.createElement("div", {
                  key: appName,
                  className: "flex flex-col gap-2"
                },
                  React.createElement("div", {
                    className: "flex items-center justify-between border-b border-border pb-2"
                  },
                    React.createElement("h3", {
                      className: "text-sm font-bold"
                    }, appName),

                    React.createElement("span", {
                      className: "text-xs text-muted-foreground"
                    }, urls.length + " monitor" + (urls.length === 1 ? "" : "s"))
                  ),

                  React.createElement("div", {
                    className: "divide-y divide-border rounded-md border border-border"
                  },
                    urls.map(function (url) {
                      const monitorInfo = monitorsSafe[url] || {};
                      const status = monitorInfo.last_status || "UNKNOWN";
                      const isUp = status === "UP";
                      const isDown = status === "DOWN";
                      const badgeVariant = isUp ? "success" : (isDown ? "destructive" : "secondary");
                      const badgeText = isUp ? "● ONLINE" : (isDown ? "● DOWN" : "○ UNKNOWN");

                      return React.createElement("div", {
                        key: url,
                        className: "flex items-center justify-between px-4 py-4"
                      },
                        React.createElement("div", {
                          className: "flex flex-col gap-1 pr-4 truncate"
                        },
                          React.createElement("span", {
                            className: "text-sm font-semibold truncate"
                          }, url),

                          React.createElement("span", {
                            className: "text-xs text-muted-foreground"
                          }, "Polling status every 60 seconds")
                        ),

                        React.createElement("div", {
                          className: "flex items-center gap-4 shrink-0"
                        },
                          React.createElement(Badge, {
                            variant: badgeVariant,
                            className: "text-xs px-2 py-0.5"
                          }, badgeText),

                          React.createElement(Button, {
                            onClick: function () {
                              handleRemove(url);
                            },
                            disabled: loading,
                            className: "text-xs border border-destructive/30 hover:bg-destructive/10 text-destructive px-3 py-1 cursor-pointer"
                          }, "🗑 Delete")
                        )
                      );
                    })
                  )
                );
              })
            )
        )
      )
    );
  }

  window.__HERMES_PLUGINS__.register("uptime", WebsiteMonitorPage);
})();