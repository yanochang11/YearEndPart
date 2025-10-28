import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Fingerprint Object Inspector", layout="centered")

st.title("Fingerprint Object Inspector 🕵️")
st.markdown("Let's look inside the object that Streamlit is returning.")

def get_fingerprint_component():
    """Renders the JavaScript component."""
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

# --- Main Logic ---
st.header("Inspection Results")

if 'component_object' not in st.session_state:
    st.session_state.component_object = None

if st.session_state.component_object is None:
    returned_value = get_fingerprint_component()
    if returned_value:
        st.session_state.component_object = returned_value
        st.rerun()

if st.session_state.component_object:
    st.success("✅ Object received from the component!")
    
    st.subheader("Object's Internal Attributes:")
    st.write(
        "We are looking for an attribute that holds the fingerprint string "
        "(a long series of letters and numbers)."
    )
    
    # This is the key part: vars() lists all internal attributes of the object.
    try:
        attributes = vars(st.session_state.component_object)
        st.json(attributes)
    except TypeError:
        st.warning("`vars()` could not inspect the object. Let's try `dir()`.")
        # As a fallback, dir() lists all methods and attributes.
        attributes = dir(st.session_state.component_object)
        st.write(attributes)

else:
    st.warning("🔄 Waiting to receive the object from the frontend...")
