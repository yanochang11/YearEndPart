import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Fingerprint URL Test", layout="centered")

st.title("Fingerprint URL 傳遞測試 🚀")
st.markdown("這個版本將使用 URL 參數來傳遞識別碼，這是最穩定的方法。")

# --- 關鍵修改：Python 檢查 URL ---
query_params = st.experimental_get_query_params()
fingerprint_from_url = query_params.get("fingerprint", [None])[0]

# --- 如果 URL 中已經有 fingerprint，代表成功了 ---
if fingerprint_from_url:
    st.success("🎉🎉🎉 最終成功！已從 URL 獲取 Fingerprint 字串！")
    st.code(fingerprint_from_url, language=None)
    st.info("現在，請將此邏輯應用回您的主程式中。")

# --- 如果 URL 中沒有，才顯示 JS 元件讓它去獲取 ---
else:
    st.warning("🔄 正在執行前端腳本以獲取 Fingerprint...")
    st.info("頁面將會自動重新整理一次。")
    
    # --- 關鍵修改：JavaScript 修改 URL ---
    js_code = """
    <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
    <script>
      (async () => {
        // 檢查 URL，如果已經有 fingerprint，就不再執行
        const currentUrl = new URL(window.location.href);
        if (currentUrl.searchParams.has('fingerprint')) {
          return;
        }

        try {
          const fp = await FingerprintJS.load();
          const result = await fp.get();
          
          // 將 fingerprint 作為 URL 參數加上去
          currentUrl.searchParams.set('fingerprint', result.visitorId);
          
          // 重新導向到新的 URL，這會觸發 Streamlit 的重新整理
          window.location.href = currentUrl.toString();

        } catch (error) {
          console.error("FingerprintJS error:", error);
          // 可以在這裡顯示錯誤訊息
        }
      })();
    </script>
    """
    components.html(js_code, height=0)
