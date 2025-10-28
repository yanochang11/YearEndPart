import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Fingerprint Test", layout="centered")

st.title("FingerprintJS 最終測試")
st.markdown("這次我們將嘗試從收到的物件中**強制提取**字串。")

def get_fingerprint_component():
    """
    渲染 JavaScript 元件來獲取設備指紋。
    """
    js_code = """
    <script src="https://cdn.jsdelivr.net/npm/@fingerprintjs/fingerprintjs@3/dist/fp.min.js"></script>
    <script>
      (function() {
        if (window.fingerprintSent) { return; }
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

if 'fingerprint_val' not in st.session_state:
    st.session_state.fingerprint_val = None

if st.session_state.fingerprint_val is None:
    component_return_value = get_fingerprint_component()
    
    if component_return_value:
        st.session_state.fingerprint_val = component_return_value
        st.rerun()

# --- 關鍵修改點 ---
if st.session_state.fingerprint_val:
    try:
        # 不再檢查型別，直接嘗試將收到的值轉換為字串
        fingerprint_str = str(st.session_state.fingerprint_val)
        
        # 簡單驗證一下轉換後的字串是否有效 (長度大於10)
        if len(fingerprint_str) > 10:
             st.success("🎉🎉🎉 最終成功！已強制提取出 Fingerprint 字串！")
             st.code(fingerprint_str, language=None)
             st.info("這就是我們需要的最終識別碼。現在可以將此邏輯應用回主程式了。")
        else:
            st.error("轉換後的字串長度不足，可能不是有效的識別碼。")
            st.write("轉換後的字串：")
            st.code(fingerprint_str)
            st.write("原始收到的資料：")
            st.code(st.session_state.fingerprint_val)

    except Exception as e:
        st.error(f"在將物件轉換為字串時發生錯誤: {e}")
        st.write("原始收到的資料：")
        st.code(st.session_state.fingerprint_val)
else:
    st.warning("🔄 正在等待從前端獲取 Fingerprint...")
