use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct FetchOptions {
    pub url: String,
    #[serde(default = "default_method")]
    pub method: String,
    #[serde(default)]
    pub headers: std::collections::HashMap<String, String>,
    #[serde(default)]
    pub body: Option<String>,
}

fn default_method() -> String {
    "GET".into()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FetchResponse {
    pub ok: bool,
    pub status: u16,
    pub status_text: String,
    pub data: String,
}

/// Proxies HTTP requests through the Rust backend (reqwest) to bypass
/// Chromium's cross-origin connection-pool limits on Linux.
#[tauri::command]
pub async fn proxy_fetch(options: FetchOptions) -> Result<FetchResponse, String> {
    let client = reqwest::Client::new();

    let method: reqwest::Method = options
        .method
        .parse()
        .map_err(|e| format!("Invalid HTTP method: {}", e))?;

    let mut req = client.request(method, &options.url);

    for (key, value) in &options.headers {
        req = req.header(key.as_str(), value.as_str());
    }

    if let Some(body) = &options.body {
        req = req.body(body.clone());
    }

    match req.send().await {
        Ok(resp) => {
            let status = resp.status().as_u16();
            let status_text = resp
                .status()
                .canonical_reason()
                .unwrap_or("Unknown")
                .to_string();
            let ok = resp.status().is_success();
            let data = resp
                .text()
                .await
                .unwrap_or_else(|_| String::new());

            Ok(FetchResponse {
                ok,
                status,
                status_text,
                data,
            })
        }
        Err(err) => {
            // If the backend isn't ready (connection refused), return a 503
            // instead of propagating the error — mirrors the Electron behavior.
            if err.is_connect() {
                Ok(FetchResponse {
                    ok: false,
                    status: 503,
                    status_text: "Service Unavailable".into(),
                    data: String::new(),
                })
            } else {
                Err(format!("HTTP request failed: {}", err))
            }
        }
    }
}
