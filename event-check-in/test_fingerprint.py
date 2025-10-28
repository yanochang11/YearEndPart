import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Fingerprint Test", layout="centered")

st.title("FingerprintJS 測試環境")
st.markdown("這個頁面只用來測試能否成功從瀏覽器獲取設備識別碼。")

def get_fingerprint_component():
    """
    渲染一個 JavaScript 元件來獲取設備指紋。
    """
    js_code = """
    <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
    <script>
      (function() {
        // 使用一個旗標來確保此腳本只執行一次
        if (window.fingerprintSent) {
          return;
        }
        window.fingerprintSent = true;

        const getAndSendFingerprint = async () => {
          try {
            // 等待 Streamlit 物件準備就緒
            while (!window.Streamlit) {
              await new Promise(resolve => setTimeout(resolve, 50));
            }

            const fp = await FingerprintJS.load();
            const result = await fp.get();
            
            // 回傳獲取到的 visitorId
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

# 呼叫元件並等待回傳值
fingerprint = get_fingerprint_component()

if fingerprint:
    st.success("🎉 成功獲取到 Fingerprint！")
    st.code(fingerprint, language=None)
    st.info("這表示前後端通訊正常。您可以將此邏輯應用回您的主程式中。")
else:
    st.warning("🔄 正在等待從前端獲取 Fingerprint...")
    st.info("如果長時間停留在此畫面，請檢查瀏覽器的開發者工具 (F12) 中的 Console 是否有錯誤訊息。")
