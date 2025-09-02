// Step 3: Implement actual MCP tools
Deno.serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
      }
    })
  }

  // Handle GET requests
  if (req.method === "GET") {
    return new Response("MCP Server is running!", {
      status: 200,
      headers: { "Content-Type": "text/plain" }
    })
  }

  // Handle POST requests
  if (req.method === "POST") {
    try {
      const payload = await req.json()
      console.log("Received payload:", payload)

      const { jsonrpc, method, params, id } = payload

      // Validate JSON-RPC 2.0 format
      if (jsonrpc !== "2.0" || typeof method !== "string" || id === undefined) {
        return new Response(JSON.stringify({
          jsonrpc: "2.0",
          id: id,
          error: { code: -32600, message: "Invalid Request" }
        }), {
          status: 400,
          headers: { "Content-Type": "application/json" }
        })
      }

      // Handle MCP methods
      switch (method) {
        case "tools/list": {
          return new Response(JSON.stringify({
            jsonrpc: "2.0",
            id: id,
            result: {
              tools: ["get_trading_status", "execute_trade", "get_performance_metrics", "update_strategy_parameters"]
            }
          }), {
            status: 200,
            headers: { "Content-Type": "application/json" }
          })
        }

        case "tools/call": {
          const { tool, arguments: args } = params ?? {}

          if (!tool) {
            return new Response(JSON.stringify({
              jsonrpc: "2.0",
              id: id,
              error: { code: -32602, message: "Tool name required" }
            }), {
              status: 400,
              headers: { "Content-Type": "application/json" }
            })
          }

          // Handle specific tools
          switch (tool) {
            case "get_trading_status": {
              const { user_id } = args ?? {}
              return new Response(JSON.stringify({
                jsonrpc: "2.0",
                id: id,
                result: {
                  user_id: user_id || "default",
                  status: "active",
                  active_positions: 0,
                  total_pnl: 0.0,
                  daily_pnl: 0.0,
                  risk_level: "low"
                }
              }), {
                status: 200,
                headers: { "Content-Type": "application/json" }
              })
            }

            case "execute_trade": {
              const { user_id, symbol, side, quantity, price } = args ?? {}
              return new Response(JSON.stringify({
                jsonrpc: "2.0",
                id: id,
                result: {
                  trade_id: "test_" + Date.now(),
                  user_id: user_id || "default",
                  symbol: symbol || "BTCUSD",
                  side: side || "buy",
                  quantity: quantity || 0.001,
                  price: price || 45000.0,
                  executed_at: new Date().toISOString()
                }
              }), {
                status: 200,
                headers: { "Content-Type": "application/json" }
              })
            }

            case "get_performance_metrics": {
              const { user_id, timeframe } = args ?? {}
              return new Response(JSON.stringify({
                jsonrpc: "2.0",
                id: id,
                result: {
                  user_id: user_id || "default",
                  timeframe: timeframe || "1d",
                  total_return: 0.0,
                  sharpe_ratio: 0.0,
                  max_drawdown: 0.0,
                  win_rate: 0.0,
                  total_trades: 0,
                  profitable_trades: 0,
                  average_trade_duration: "0h",
                  last_updated: new Date().toISOString()
                }
              }), {
                status: 200,
                headers: { "Content-Type": "application/json" }
              })
            }

            case "update_strategy_parameters": {
              const { user_id, strategy_name, parameters } = args ?? {}
              return new Response(JSON.stringify({
                jsonrpc: "2.0",
                id: id,
                result: {
                  user_id: user_id || "default",
                  strategy_name: strategy_name || "default_strategy",
                  parameters: parameters || {},
                  updated_at: new Date().toISOString(),
                  status: "updated"
                }
              }), {
                status: 200,
                headers: { "Content-Type": "application/json" }
              })
            }

            default: {
              return new Response(JSON.stringify({
                jsonrpc: "2.0",
                id: id,
                error: { code: -32601, message: `Tool "${tool}" not found` }
              }), {
                status: 400,
                headers: { "Content-Type": "application/json" }
              })
            }
          }
        }

        case "initialize": {
          const { session_id, user_id } = params ?? {}
          return new Response(JSON.stringify({
            jsonrpc: "2.0",
            id: id,
            result: {
              message: "Initialized successfully",
              session_id: session_id || "default",
              user_id: user_id || "default"
            }
          }), {
            status: 200,
            headers: { "Content-Type": "application/json" }
          })
        }

        default: {
          return new Response(JSON.stringify({
            jsonrpc: "2.0",
            id: id,
            error: { code: -32601, message: `Method "${method}" not found` }
          }), {
            status: 400,
            headers: { "Content-Type": "application/json" }
          })
        }
      }

    } catch (error) {
      console.error("Error parsing JSON:", error)
      return new Response(JSON.stringify({
        jsonrpc: "2.0",
        id: null,
        error: { code: -32700, message: "Parse error" }
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      })
    }
  }

  // Method not allowed
  return new Response(JSON.stringify({
    jsonrpc: "2.0",
    id: null,
    error: { code: -32600, message: "Method Not Allowed" }
  }), {
    status: 405,
    headers: { "Content-Type": "application/json" }
  })
})
