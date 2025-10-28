import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Fingerprint Test", layout="centered")

st.title("FingerprintJS 測試環境 (修正版)")
st.markdown("這個版本會明確地顯示獲取到的**識別碼字串**。")

def get_fingerprint_component():
    """
    渲染一個 JavaScript 元件來獲取設備指紋。
    """
    js_code = """
    <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
    <script>
      (function() {
        if (window.fingerprintSent) {
          return;
        }
        window.fingerprintSent = true;

        const getAndSendFingerprint = async () => {
          try {
            while (!window.Streamlit) {
              await new Promise(resolve => setTimeout(resolve, 50));
            }

            const fp = await FingerprintJS.load();
            const result = await fp.get();
            window.Streamlit.setComponentValue(result.visitorId);

          } catch (error) {
            console.error("FingerprintJS error:", error);
            if (window.Streamlit) {
              window.Streamlit.setComponentValue({ "error": error.message });
            }
          }
        };

        getAndSendFingerprint();
      })();
    </script>
    """
    return components.html(js_code, height=0)


# --- 主程式邏輯 ---
st.header("測試結果")

# 初始化 session_state
if 'fingerprint_val' not in st.session_state:
    st.session_state.fingerprint_val = None

# 只有在還沒有拿到值的時候，才呼叫元件
if st.session_state.fingerprint_val is None:
    component_return_value = get_fingerprint_component()
    
    # 如果元件有回傳值了，就存起來並重新整理頁面
    if component_return_value:
        st.session_state.fingerprint_val = component_return_value
        st.rerun()

# 檢查最終結果
if st.session_state.fingerprint_val:
    # 檢查收到的值是不是一個字串
    if isinstance(st.session_state.fingerprint_val, str):
        st.success("🎉 成功獲取到 Fingerprint 字串！")
        st.code(st.session_state.fingerprint_val, language=None)
        st.info("這串由數字和字母組成的就是我們需要的設備識別碼。")
    else:
        st.error("收到的資料不是字串格式，請檢查。")
        st.write("收到的原始資料：")
        st.code(st.session_state.fingerprint_val, language=None)
else:
    st.warning("🔄 正在等待從前端獲取 Fingerprint...")
