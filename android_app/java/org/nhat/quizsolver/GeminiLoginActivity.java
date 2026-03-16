package org.nhat.quizsolver;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.File;
import java.io.FileWriter;

/**
 * WebView Activity for Gemini Login
 * Automatically extracts cookies after successful login
 */
public class GeminiLoginActivity extends Activity {

    private static final String TAG = "GeminiLogin";
    private static final String GEMINI_URL = "https://gemini.google.com/app";
    private static final String ACCOUNTS_URL = "https://accounts.google.com";

    private WebView webView;
    private boolean cookieSaved = false;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Create WebView
        webView = new WebView(this);
        setContentView(webView);

        // Configure WebView settings
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setUserAgentString(
                "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36");

        // Enable cookies
        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, true);

        // Set WebViewClient to intercept navigation
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                Log.d(TAG, "Loading: " + url);
                return false; // Let WebView handle it
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                Log.d(TAG, "Page finished: " + url);

                // Check if we're on Gemini (not login page)
                if (url.contains("gemini.google.com") && !url.contains("accounts.google.com")) {
                    checkAndSaveCookies();
                }
            }
        });

        // Set WebChromeClient for progress
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                if (newProgress == 100) {
                    // Page fully loaded
                    String url = view.getUrl();
                    if (url != null && url.contains("gemini.google.com")) {
                        checkAndSaveCookies();
                    }
                }
            }
        });

        // Load Gemini
        webView.loadUrl(GEMINI_URL);

        Toast.makeText(this, "Đăng nhập Google để tiếp tục", Toast.LENGTH_LONG).show();
    }

    /**
     * Check for and save Gemini cookies
     */
    private void checkAndSaveCookies() {
        if (cookieSaved)
            return;

        CookieManager cookieManager = CookieManager.getInstance();
        String cookies = cookieManager.getCookie("https://gemini.google.com");

        if (cookies == null || cookies.isEmpty()) {
            Log.d(TAG, "No cookies yet");
            return;
        }

        Log.d(TAG, "Cookies: " + cookies);

        // Look for __Secure-1PSID
        String psid = extractCookie(cookies, "__Secure-1PSID");

        if (psid != null && !psid.isEmpty()) {
            Log.i(TAG, "Found __Secure-1PSID cookie!");

            // Save to file
            saveCookiesToFile(cookies);

            cookieSaved = true;

            Toast.makeText(this, "Đăng nhập thành công!", Toast.LENGTH_SHORT).show();

            // Return to main app
            Intent resultIntent = new Intent();
            resultIntent.putExtra("cookies", cookies);
            resultIntent.putExtra("psid", psid);
            setResult(RESULT_OK, resultIntent);

            // Finish after a short delay
            webView.postDelayed(() -> finish(), 1500);
        }
    }

    /**
     * Extract a specific cookie value
     */
    private String extractCookie(String cookieString, String name) {
        String[] cookies = cookieString.split(";");
        for (String cookie : cookies) {
            String[] parts = cookie.trim().split("=", 2);
            if (parts.length == 2 && parts[0].equals(name)) {
                return parts[1];
            }
        }
        return null;
    }

    /**
     * Save cookies to a JSON file in app's private storage
     */
    private void saveCookiesToFile(String cookieString) {
        try {
            // Parse cookies into JSON format
            StringBuilder json = new StringBuilder("{");
            String[] cookies = cookieString.split(";");
            boolean first = true;

            for (String cookie : cookies) {
                String[] parts = cookie.trim().split("=", 2);
                if (parts.length == 2) {
                    if (!first)
                        json.append(",");
                    json.append("\"").append(parts[0]).append("\":\"").append(parts[1]).append("\"");
                    first = false;
                }
            }
            json.append("}");

            // Save to file
            File filesDir = getFilesDir();
            File cookieFile = new File(filesDir, "gemini_cookies.json");

            FileWriter writer = new FileWriter(cookieFile);
            writer.write(json.toString());
            writer.close();

            Log.i(TAG, "Cookies saved to: " + cookieFile.getAbsolutePath());

        } catch (Exception e) {
            Log.e(TAG, "Failed to save cookies: " + e.getMessage());
        }
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            setResult(RESULT_CANCELED);
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}
