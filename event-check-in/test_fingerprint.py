import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Minimal JS Test", layout="centered")

st.title("最低限度 JavaScript 執行測試 🛠️")
st.markdown("此測試不載入任何外部函式庫，只驗證 JS 是否能修改 URL。")

# --- 檢查 URL ---
# st.query_params is a dictionary-like object
test_result = st.query_params.get("test_result")

# --- 如果 URL 中已經有 test_result，代表成功了 ---
if test_result == "success":
    st.success("🎉🎉🎉 測試通過！")
    st.info("這證明了您的環境可以執行簡單的 JavaScript 來修改 URL。")
    st.warning("問題根源確認：您的環境很可能阻止了外部 FingerprintJS 函式庫的載入。")

# --- 如果 URL 中沒有，才顯示 JS 元件讓它去執行 ---
else:
    st.warning("🔄 正在執行最簡單的前端腳本...")
    st.info("頁面應該會在一兩秒後自動重新整理。如果沒有，請手動重新整理一次。")
    
    # --- 最簡單的 JavaScript，不含任何外部函式庫 ---
    js_code = """
    <script>
      (async () => {
        // 使用旗標確保不重複執行
        if (window.jsTestExecuted) {
            return;
        }
        window.jsTestExecuted = true;

        try {
            // 直接修改 URL
            const currentUrl = new URL(window.location.href);
            currentUrl.searchParams.set('test_result', 'success');
            
            // 重新導向到新的 URL
            window.location.href = currentUrl.toString();

        } catch (error) {
            console.error("Minimal JS Test error:", error);
        }
      })();
    </script>
    """
    components.html(js_code, height=0)
