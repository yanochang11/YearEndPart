import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Device Fingerprint Test", layout="centered")

st.title("裝置指紋獲取測試 (最終版)")
st.markdown("""
這是使用前端 FingerprintJS 函式庫的最終測試版本。
它在一個標準的 Streamlit 環境中應該可以成功執行。
""")

def get_fingerprint_component():
    """
    渲染 JavaScript 元件來獲取並回傳裝置指紋。
    """
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
            // 等待 Streamlit 物件準備就緒
            while (!window.Streamlit) {
              await new Promise(resolve => setTimeout(resolve, 50));
            }

            const fp = await FingerprintJS.load();
            const result = await fp.get();
            
            // 使用 setComponentValue 將值傳回 Python 後端
            window.Streamlit.setComponentValue(result.visitorId);

        } catch (error) {
            console.error("FingerprintJS error:", error);
            window.Streamlit.setComponentValue({ "error": error.message });
        }
      })();
    </script>
    """
    return components.html(js_code, height=0)


# --- 主程式邏輯 ---
st.header("測試結果")

# 初始化 session_state
if 'fingerprint_id' not in st.session_state:
    st.session_state.fingerprint_id = None

# 只有在還沒有拿到值的時候，才呼叫元件
if st.session_state.fingerprint_id is None:
    component_return_value = get_fingerprint_component()
    
    # 如果元件有回傳值了，就存起來並重新整理頁面
    if component_return_value:
        st.session_state.fingerprint_id = component_return_value
        st.rerun()

# 檢查最終結果
if st.session_state.fingerprint_id:
    # 檢查收到的值是不是一個字串
    if isinstance(st.session_state.fingerprint_id, str):
        st.success("🎉 成功獲取到 Fingerprint 字串！")
        st.code(st.session_state.fingerprint_id, language=None)
    else:
        st.error("收到的資料不是字串格式。")
        st.write("這再次證實了您的開發環境阻止了前端腳本的正常執行。")
        st.write("收到的原始資料：")
        st.code(st.session_state.fingerprint_id)
else:
    st.warning("🔄 正在等待前端腳本執行並回傳 Fingerprint...")
    st.info("如果長時間停留在此畫面，即表示前端腳本被您的開發環境封鎖，無法執行。")
