package com.example.courtmatepickleballcourtmanager.repository;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URI;
import java.nio.charset.StandardCharsets;

/** Remote bookings are centralized server records, NOT synchronized SQLite local bookings. */
public final class CloudBookingRepository {
    private final String baseUrl;
    private final String bearer;
    private final String role;
    private final boolean legacy;
    public CloudBookingRepository(String url, String token) {
        this(url, token, "ADMIN", true);
    }
    private CloudBookingRepository(String url, String token, String role, boolean legacy) {
        String normalized = url == null ? "" : url.trim().replaceAll("/+$", "");
        try {
            URI parsed = URI.create(normalized);
            if (!"https".equals(parsed.getScheme()) || parsed.getHost() == null
                    || parsed.getRawUserInfo() != null || parsed.getRawQuery() != null
                    || parsed.getRawFragment() != null) {
                throw new IllegalArgumentException("Máy chủ phải dùng HTTPS hợp lệ");
            }
        } catch (RuntimeException e) {
            throw new IllegalArgumentException("Máy chủ phải dùng HTTPS hợp lệ", e);
        }
        if (token == null || token.trim().length() < 32) {
            throw new IllegalArgumentException("Token quản trị không hợp lệ");
        }
        this.baseUrl = normalized;
        this.bearer = token.trim();
        this.role = role;
        this.legacy = legacy;
    }

    /** Credentials are used for a single HTTPS request; only the short-lived bearer is retained. */
    public static CloudBookingRepository login(String server, String username, String password) throws Exception {
        String base = server == null ? "" : server.trim().replaceAll("/+$", "");
        URI uri;
        try { uri = URI.create(base); }
        catch (RuntimeException e) { throw new IllegalArgumentException("Máy chủ HTTPS không hợp lệ", e); }
        if (!"https".equals(uri.getScheme()) || uri.getHost() == null
                || uri.getRawUserInfo() != null || uri.getRawQuery() != null || uri.getRawFragment() != null)
            throw new IllegalArgumentException("Máy chủ phải sử dụng HTTPS");
        HttpURLConnection conn = (HttpURLConnection) new URL(base + "/v1/auth/login").openConnection();
        try {
            conn.setInstanceFollowRedirects(false);
            conn.setConnectTimeout(10_000);
            conn.setReadTimeout(15_000);
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setRequestProperty("Accept", "application/json");
            JSONObject request = new JSONObject().put("username", username).put("password", password);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(request.toString().getBytes(StandardCharsets.UTF_8));
            }
            int code = conn.getResponseCode();
            try (InputStream in = code >= 400 ? conn.getErrorStream() : conn.getInputStream()) {
                if (in == null) throw new IllegalStateException("Máy chủ không trả dữ liệu đăng nhập");
                ByteArrayOutputStream buffer = new ByteArrayOutputStream();
                byte[] chunk = new byte[4096];
                int n;
                while ((n = in.read(chunk)) != -1) {
                    if (buffer.size() + n > 16_384) throw new IllegalStateException("Phản hồi đăng nhập quá lớn");
                    buffer.write(chunk, 0, n);
                }
                JSONObject data = new JSONObject(buffer.toString("UTF-8"));
                if (code < 200 || code >= 300)
                    throw new IllegalStateException("Đăng nhập cloud thất bại (HTTP " + code + "): "
                            + data.optString("detail", "Kiểm tra tài khoản và mật khẩu"));
                String role = data.getString("role");
                if (!"ADMIN".equals(role) && !"STAFF".equals(role))
                    throw new IllegalStateException("Vai trò cloud không hợp lệ");
                return new CloudBookingRepository(base, data.getString("access_token"), role, false);
            }
        } finally { conn.disconnect(); }
    }

    public boolean isAdmin() { return "ADMIN".equals(role); }
    public String role() { return role; }
    public void logout() throws Exception { if (!legacy) request("POST", "/v1/auth/logout", null); }

    private String request(String method, String path, JSONObject body) throws Exception {
        URL url = new URL(baseUrl + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        try {
            conn.setInstanceFollowRedirects(false); // Do not leak Authorization to redirects.
            conn.setRequestMethod(method);
            conn.setConnectTimeout(10_000);
            conn.setReadTimeout(15_000);
            conn.setRequestProperty("Accept", "application/json");
            conn.setRequestProperty("Authorization", "Bearer " + bearer);
            if (body != null) {
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                conn.setDoOutput(true);
                try (OutputStream out = conn.getOutputStream()) {
                    out.write(body.toString().getBytes(StandardCharsets.UTF_8));
                }
            }
            int code = conn.getResponseCode();
            try (InputStream in = code >= 400 ? conn.getErrorStream() : conn.getInputStream()) {
                String content = "";
                if (in != null) {
                    ByteArrayOutputStream buffer = new ByteArrayOutputStream();
                    byte[] block = new byte[4096];
                    int bytes;
                    while ((bytes = in.read(block)) != -1) {
                        if (buffer.size() + bytes > 1_000_000)
                            throw new IllegalStateException("Phản hồi máy chủ vượt giới hạn");
                        buffer.write(block, 0, bytes);
                    }
                    content = buffer.toString("UTF-8");
                }
                if (code < 200 || code >= 300) {
                    String reason = "Yêu cầu thất bại";
                    try { reason = new JSONObject(content).optString("detail", reason); }
                    catch (Exception ignored) { /* Do not crash on non-JSON server errors */ }
                    throw new IllegalStateException("HTTP " + code + ": " + reason);
                }
                return content;
            }
        } finally {
            conn.disconnect();
        }
    }
    public JSONArray courts() throws Exception {
        return new JSONArray(request("GET", "/v1/admin/courts", null));
    }
    public JSONObject createCourt(String name, int priceHour) throws Exception {
        return new JSONObject(request("POST", "/v1/admin/courts",
                new JSONObject().put("name", name).put("price_hour", priceHour)));
    }
    public JSONObject summary() throws Exception { return summary(null); }
    public JSONObject summary(String day) throws Exception {
        return new JSONObject(request("GET", "/v1/admin/summary"
                + (day == null ? "" : "?date=" + validatedDay(day)), null));
    }
    private static String validatedDay(String date) {
        if (!date.matches("\\d{4}-\\d{2}-\\d{2}"))
            throw new IllegalArgumentException("Ngày phải là YYYY-MM-DD");
        return date;
    }
    public JSONObject updateCourtActive(int id, boolean active) throws Exception {
        return new JSONObject(request("POST", "/v1/admin/courts/" + id + "/update",
                new JSONObject().put("active", active)));
    }
    public JSONArray bookings() throws Exception {
        return new JSONArray(request("GET", "/v1/admin/bookings", null));
    }
    public JSONArray bookingsForDate(String day) throws Exception {
        return bookingsForDate(day, 0, 200);
    }
    public JSONArray bookingsForDate(String day, int offset, int limit) throws Exception {
        if (offset < 0 || offset > 100_000 || limit < 1 || limit > 200)
            throw new IllegalArgumentException("Trang lịch không hợp lệ");
        return new JSONArray(request("GET", "/v1/admin/bookings?date=" + validatedDay(day)
                + "&limit=" + limit + "&offset=" + offset, null));
    }
    /** Server-side ordered cursor. Not a local SQLite sync operation. */
    public JSONObject changes(long after, int limit) throws Exception {
        if (after < 0 || limit < 1 || limit > 200)
            throw new IllegalArgumentException("Cursor không hợp lệ");
        return new JSONObject(request("GET", "/v1/admin/changes?after=" + after
                + "&limit=" + limit, null));
    }
    public JSONObject create(JSONObject values) throws Exception {
        return new JSONObject(request("POST", "/v1/admin/bookings", values));
    }
    public JSONObject updateStatus(int id, String status) throws Exception {
        // PATCH support added to backend; do not use GET to change booking state.
        return new JSONObject(request("POST", "/v1/admin/bookings/" + id + "/status",
                new JSONObject().put("status", status)));
    }
    public JSONObject bankIntent(int id) throws Exception {
        return new JSONObject(request("POST", "/v1/admin/bookings/" + id + "/bank-intent", null));
    }
}
