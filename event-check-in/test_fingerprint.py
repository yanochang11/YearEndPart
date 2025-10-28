import streamlit as st
import streamlit.components.v1 as components
import time

st.set_page_config(page_title="Fingerprint URL Test", layout="centered")

st.title("Fingerprint URL 傳遞測試 (最終版)")
st.markdown("已更新為 `st.query_params`，這是最穩定的方法。")

# --- 關鍵修改：使用最新的 st.query_params ---
# st.query_params is a dictionary-like object
fingerprint_from_url = st.query_params.get("fingerprint")

# --- 如果 URL 中已經有 fingerprint，代表成功了 ---
if fingerprint_from_url:
    st.success("🎉🎉🎉 最終成功！已從 URL 獲取 Fingerprint 字串！")
    st.code(fingerprint_from_url, language=None)
    st.info("現在，請將此邏輯應用回您的主程式中。")

# --- 如果 URL 中沒有，才顯示 JS 元件讓它去獲取 ---
else:
    st.warning("🔄 正在執行前端腳本以獲取 Fingerprint...")
    st.info("頁面應該會在一兩秒後自動重新整理。如果沒有，請手動重新整理一次。")
    
    # --- JavaScript 邏輯不變 ---
    js_code = """
    <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
    <script>
      (async () => {
        // 使用旗標確保不重複執行
        if (window.fingerprintJsExecuted) {
            return;
        }
        window.fingerprintJsExecuted = true;

        try {
            const fp = await FingerprintJS.load();
            const result = await fp.get();
            
            const currentUrl = new URL(window.location.href);
            currentUrl.searchParams.set('fingerprint', result.visitorId);
            
            // 重新導向到新的 URL，這會觸發 Streamlit 的重新整理
            window.location.href = currentUrl.toString();

        } catch (error) {
            console.error("FingerprintJS error:", error);
        }
      })();
    </script>
    """
    components.html(js_code, height=0)
