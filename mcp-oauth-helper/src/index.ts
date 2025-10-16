#!/usr/bin/env node
/**
 * MCP OAuth Helper - Uses official MCP SDK for OAuth flows
 * This mimics how the MCP Inspector handles OAuth for any MCP server
 */

import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import {
  auth,
  discoverOAuthProtectedResourceMetadata,
  discoverAuthorizationServerMetadata,
  type OAuthClientProvider,
} from "@modelcontextprotocol/sdk/client/auth.js";
import {
  type OAuthClientInformation,
  type OAuthTokens,
  type OAuthClientMetadata,
  type OAuthMetadata,
} from "@modelcontextprotocol/sdk/shared/auth.js";
import { randomBytes } from "crypto";
import { createServer, IncomingMessage, ServerResponse } from "http";
import { URL } from "url";
import { readFile, writeFile } from "fs/promises";
import { homedir } from "os";
import { join } from "path";

/**
 * Simple file-based OAuth client provider for CLI usage
 * Stores tokens and client info in ~/.mcp-oauth-tokens.json
 */
class FileBasedOAuthClientProvider implements OAuthClientProvider {
  private tokensFile = join(homedir(), ".mcp-oauth-tokens.json");
  private callbackPort = 8080;
  private callbackPath = "/callback";
  private scope: string;
  private serverUrl: URL;
  private _state?: string;
  private _codeVerifier?: string;
  private _clientInfo?: OAuthClientInformation;
  private _tokens?: OAuthTokens;

  constructor(serverUrl: URL, scope?: string) {
    this.serverUrl = serverUrl;
    this.scope = scope || "";
  }

  get redirectUrl(): string {
    return `http://localhost:${this.callbackPort}${this.callbackPath}`;
  }

  get redirect_uris(): string[] {
    return [this.redirectUrl];
  }

  get clientMetadata(): OAuthClientMetadata {
    return {
      redirect_uris: this.redirect_uris,
      token_endpoint_auth_method: "none",
      grant_types: ["authorization_code", "refresh_token"],
      response_types: ["code"],
      client_name: "YAML MCP Agent System",
      client_uri: "https://github.com/your-repo",
      scope: this.scope,
    };
  }

  state(): string {
    if (!this._state) {
      this._state = randomBytes(32).toString("hex");
    }
    return this._state;
  }

  async clientInformation(): Promise<OAuthClientInformation | undefined> {
    if (this._clientInfo) {
      return this._clientInfo;
    }
    // Try to load from file
    try {
      const data = await readFile(this.tokensFile, "utf-8");
      const stored = JSON.parse(data);
      const serverKey = this.serverUrl.toString();
      if (stored[serverKey]?.clientInfo) {
        this._clientInfo = stored[serverKey].clientInfo;
        return this._clientInfo;
      }
    } catch {
      // File doesn't exist or is invalid
    }
    return undefined;
  }

  saveClientInformation(clientInfo: OAuthClientInformation): void {
    this._clientInfo = clientInfo;
    // Will be saved with tokens
  }

  async tokens(): Promise<OAuthTokens | undefined> {
    if (this._tokens) {
      return this._tokens;
    }
    // Try to load from file
    try {
      const data = await readFile(this.tokensFile, "utf-8");
      const stored = JSON.parse(data);
      const serverKey = this.serverUrl.toString();
      if (stored[serverKey]?.tokens) {
        this._tokens = stored[serverKey].tokens;
        return this._tokens;
      }
    } catch {
      // File doesn't exist or is invalid
    }
    return undefined;
  }

  saveTokens(tokens: OAuthTokens): void {
    this._tokens = tokens;
    // Save to file
    this.saveToFile().catch(console.error);
  }

  private async saveToFile(): Promise<void> {
    try {
      let stored: any = {};
      try {
        const data = await readFile(this.tokensFile, "utf-8");
        stored = JSON.parse(data);
      } catch {
        // File doesn't exist yet
      }

      const serverKey = this.serverUrl.toString();
      stored[serverKey] = {
        clientInfo: this._clientInfo,
        tokens: this._tokens,
        updatedAt: new Date().toISOString(),
      };

      await writeFile(this.tokensFile, JSON.stringify(stored, null, 2));
    } catch (error) {
      console.error("Failed to save OAuth tokens:", error);
    }
  }

  redirectToAuthorization(authUrl: URL): void {
    console.log("\n🔐 OAuth Authorization Required");
    console.log("=" .repeat(60));
    console.log("Please authorize this application in your browser:");
    console.log(`\n${authUrl.href}\n`);
    console.log("=" .repeat(60));
    console.log("Waiting for authorization...\n");

    // Try to open browser automatically
    import("open").then((openModule) => {
      openModule.default(authUrl.href).catch(() => {
        // Silently fail if can't open browser
      });
    }).catch(() => {
      // open module not available, that's fine
    });
  }

  saveCodeVerifier(verifier: string): void {
    this._codeVerifier = verifier;
  }

  codeVerifier(): string {
    if (!this._codeVerifier) {
      throw new Error("No code verifier saved");
    }
    return this._codeVerifier;
  }

  clear(): void {
    this._state = undefined;
    this._codeVerifier = undefined;
    this._clientInfo = undefined;
    this._tokens = undefined;
  }
}

/**
 * Start callback server and wait for OAuth callback
 */
async function waitForCallback(
  port: number,
  path: string,
  expectedState: string,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const server = createServer((req: IncomingMessage, res: ServerResponse) => {
      if (req.url?.startsWith(path)) {
        const url = new URL(req.url, `http://localhost:${port}`);
        const code = url.searchParams.get("code");
        const state = url.searchParams.get("state");
        const error = url.searchParams.get("error");

        if (error) {
          const errorDesc = url.searchParams.get("error_description");
          res.writeHead(400, { "Content-Type": "text/html" });
          res.end(`
            <html><body>
              <h1>❌ Authorization Failed</h1>
              <p>${error}: ${errorDesc || "Unknown error"}</p>
              <p>You can close this window.</p>
            </body></html>
          `);
          server.close();
          reject(new Error(`OAuth error: ${error} - ${errorDesc}`));
          return;
        }

        if (code && state === expectedState) {
          res.writeHead(200, { "Content-Type": "text/html" });
          res.end(`
            <html><body>
              <h1>✅ Authorization Successful!</h1>
              <p>You can close this window and return to your terminal.</p>
              <script>setTimeout(() => window.close(), 2000);</script>
            </body></html>
          `);
          server.close();
          resolve(code);
          return;
        }

        res.writeHead(400, { "Content-Type": "text/html" });
        res.end(`
          <html><body>
            <h1>⚠️ Invalid Callback</h1>
            <p>Missing or invalid authorization code.</p>
          </body></html>
        `);
        server.close();
        reject(new Error("Invalid callback parameters"));
      }
    });

    server.listen(port, () => {
      console.log(`Callback server listening on http://localhost:${port}${path}`);
    });

    // Timeout after 5 minutes
    setTimeout(() => {
      server.close();
      reject(new Error("Authorization timeout"));
    }, 300000);
  });
}

/**
 * Test connection to MCP server and perform OAuth if needed
 */
async function testConnection(serverUrl: string): Promise<void> {
  const url = new URL(serverUrl);

  console.log(`\n🔗 Testing connection to: ${serverUrl}`);

  // Try to connect without auth and initialize a client session
  const transport = new StreamableHTTPClientTransport(url);
  
  try {
    // Try to connect - this will throw if 401 is returned
    const Client = (await import("@modelcontextprotocol/sdk/client/index.js")).Client;
    const client = new Client({
      name: "mcp-oauth-tester",
      version: "1.0.0",
    }, {
      capabilities: {}
    });
    
    await client.connect(transport);
    
    console.log("✅ Connected successfully (no OAuth required)");
    await client.close();
    return;
  } catch (error: any) {
    // Check if it's a 401 error
    if (error.code !== 401 && !error.message?.includes("401") && !error.message?.includes("Unauthorized")) {
      console.error("❌ Connection failed:", error.message);
      throw error;
    }

    console.log("🔒 Server requires OAuth authentication");
    console.log(`   Error: ${error.message}`);
  }

  // Discover OAuth metadata
  let scope: string | undefined;
  try {
    const resourceMetadata = await discoverOAuthProtectedResourceMetadata(url);
    const authMetadata = await discoverAuthorizationServerMetadata(url);
    
    // Prefer resource metadata scopes
    const scopes = resourceMetadata?.scopes_supported || authMetadata?.scopes_supported;
    if (scopes && scopes.length > 0) {
      scope = scopes.join(" ");
      console.log(`📋 Discovered scopes: ${scope}`);
    }
  } catch (error) {
    console.log("⚠️  Could not discover OAuth metadata, using default scopes");
  }

  // Create OAuth provider
  const provider = new FileBasedOAuthClientProvider(url, scope);

  // Perform OAuth flow
  console.log("\n🔐 Starting OAuth flow...");
  const result = await auth(provider, { serverUrl: url, scope });

  if (result === "AUTHORIZED") {
    console.log("\n✅ OAuth authorization successful!");
    console.log(`💾 Tokens saved to: ${join(homedir(), ".mcp-oauth-tokens.json")}`);
    
    // Try connecting again with auth
    const tokens = await provider.tokens();
    if (tokens) {
      const authedTransport = new StreamableHTTPClientTransport(url, {
        requestInit: {
          headers: {
            Authorization: `Bearer ${tokens.access_token}`,
          },
        },
      });
      await authedTransport.start();
      console.log("✅ Successfully connected with OAuth token");
      await authedTransport.close();
    }
  } else {
    throw new Error("OAuth authorization failed");
  }
}

/**
 * Get OAuth token for a server
 */
async function getToken(serverUrl: string): Promise<string | null> {
  const url = new URL(serverUrl);
  const provider = new FileBasedOAuthClientProvider(url);
  
  const tokens = await provider.tokens();
  if (tokens) {
    return tokens.access_token;
  }
  
  return null;
}

// CLI interface
const args = process.argv.slice(2);
const command = args[0];
const serverUrl = args[1];

if (!command || !serverUrl) {
  console.error("Usage:");
  console.error("  node dist/index.js test <server-url>    # Test connection and perform OAuth if needed");
  console.error("  node dist/index.js token <server-url>   # Get existing token");
  process.exit(1);
}

try {
  if (command === "test") {
    await testConnection(serverUrl);
  } else if (command === "token") {
    const token = await getToken(serverUrl);
    if (token) {
      console.log(token);
    } else {
      console.error("No token found. Run 'test' command first.");
      process.exit(1);
    }
  } else {
    console.error(`Unknown command: ${command}`);
    process.exit(1);
  }
} catch (error: any) {
  console.error("\n❌ Error:", error.message);
  process.exit(1);
}

