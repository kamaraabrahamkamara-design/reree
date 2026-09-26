import io
import hashlib
import pandas as pd
import streamlit as st
from supabase import create_client, Client

# --- SUPABASE CONNECTION SETUP ---
SUPABASE_URL = st.secrets.get("supabase_url", "")
SUPABASE_KEY = st.secrets.get("supabase_key", "")

@st.cache_resource
def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("❌ Supabase secrets are missing! Check your secrets.toml file.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase_client()

# Standard database columns
REQUIRED_COLUMNS = ["id", "class", "subject", "period", "semester", "grade", "password_hash"]

def hash_password(password: str) -> str:
    """Hash password string using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="Academic Records Portal", layout="wide")
st.title("🏫 Academic Records Portal")
st.write("Welcome to the Student and Admin Grades Management System.")

tab_student, tab_admin = st.tabs(["🎓 Student Portal", "🔐 Admin Dashboard"])

# --- STUDENT PORTAL ---
with tab_student:
    st.header("Student Grade Inquiry")
    
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        student_id = st.text_input("Enter Student ID:", key="stu_id_input").strip()
    with col_input2:
        student_pass = st.text_input("Enter Password:", type="password", key="stu_pass_input").strip()
    
    auth_key = f"authenticated_{student_id}"
    
    if st.button("Access Dashboard", key="btn_student_login"):
        if student_id and student_pass:
            hashed_input = hash_password(student_pass)
            
            # Authenticate directly against Supabase database
            try:
                response = supabase.table("reportcard") \
                    .select("id") \
                    .eq("id", student_id) \
                    .eq("password_hash", hashed_input) \
                    .execute()
                
                if response.data:
                    st.success(f"✅ Welcome Back, Student ID: {student_id}")
                    st.session_state[auth_key] = True
                else:
                    st.error("❌ Invalid Student ID or Password.")
                    st.session_state[auth_key] = False
            except Exception as e:
                st.error(f"❌ Database error: {str(e)}")
        else:
            st.warning("⚠️ Both Student ID and Password are required.")

    # Render dashboard if session is authenticated
    if st.session_state.get(auth_key, False):
        try:
            student_data = supabase.table("reportcard").select("*").eq("id", student_id).execute()
            student_rows = pd.DataFrame(student_data.data)
            
            if not student_rows.empty:
                student_rows['grade'] = pd.to_numeric(student_rows['grade'], errors='coerce')
                
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    semesters = ["All Semesters"] + sorted(student_rows['semester'].dropna().astype(str).unique().tolist())
                    selected_semester = st.selectbox("Filter by Semester", semesters, key="student_sem_filter")
                with col_f2:
                    periods = ["All Periods"] + sorted(student_rows['period'].dropna().astype(str).unique().tolist())
                    selected_period = st.selectbox("Filter by Period", periods, key="student_per_filter")
                
                filtered_df = student_rows.copy()
                if selected_semester != "All Semesters":
                    filtered_df = filtered_df[filtered_df['semester'].astype(str) == selected_semester]
                if selected_period != "All Periods":
                    filtered_df = filtered_df[filtered_df['period'].astype(str) == selected_period]
                    
                st.subheader("📊 Academic Performance Summary")
                metric_col1, metric_col2, metric_col3 = st.columns(3)
                
                current_avg = filtered_df['grade'].mean()
                with metric_col1:
                    if pd.isna(current_avg):
                        st.metric(label="Current Filtered Average", value="N/A")
                    else:
                        st.metric(label="Current Filtered Average", value=f"{current_avg:.2f}%")
                        
                with metric_col2:
                    st.markdown("**Average by Semester**")
                    sem_avg = student_rows.groupby('semester')['grade'].mean().reset_index()
                    for _, row in sem_avg.iterrows():
                        st.write(f"• **{row['semester']}**: {row['grade']:.2f}%")
                        
                with metric_col3:
                    st.markdown("**Average by Period**")
                    per_avg = student_rows.groupby('period')['grade'].mean().reset_index()
                    for _, row in per_avg.iterrows():
                        st.write(f"• **{row['period']}**: {row['grade']:.2f}%")
                
                st.divider()
                st.subheader("Your Academic Record Matrix")
                
                display_df = filtered_df.drop(columns=['password_hash', 'created_at'], errors='ignore')
                
                if not display_df.empty:
                    try:
                        # Pivot table generation
                        pivot_df = display_df.pivot_table(
                            index='subject',
                            columns=['semester', 'period'],
                            values='grade',
                            aggfunc='mean'
                        )
                        pivot_df['Subject Average'] = pivot_df.mean(axis=1)
                        
                        st.dataframe(
                            pivot_df.style.format("{:.2f}%", na_rep="-"),
                            use_container_width=True
                        )
                        
                    except Exception as pivot_err:
                        st.error(f"❌ Could not build matrix layout: {str(pivot_err)}")
                        st.dataframe(display_df, use_container_width=True)
                        pivot_df = None
                else:
                    st.info("💡 No records match the selected filters.")
                    pivot_df = None
                
                # --- EXPORT & DOWNLOAD ---
                dl_col1, dl_col2 = st.columns(2)
                with dl_col1:
                    csv_buffer = io.StringIO()
                    if pivot_df is not None:
                        pivot_df.to_csv(csv_buffer)
                        csv_buffer.write("\n\n--- OFFICIAL VERIFICATION ---\n")
                        csv_buffer.write("Principal / Administrator Signature: ___________________________\n")
                        csv_buffer.write("Official Institutional Stamp Area:  [ STAMP PLACEHOLDER ]\n")
                        csv_buffer.write("Date of Issuance:                   ___________________________\n")
                    else:
                        display_df.to_csv(csv_buffer, index=False)
                        
                    csv_bytes = csv_buffer.getvalue().encode("utf-8")
                        
                    st.download_button(
                        label="📥 Download Pivoted Transcript Matrix (CSV)",
                        data=csv_bytes,
                        file_name=f"Transcript_Matrix_{student_id}.csv",
                        mime="text/csv; charset=utf-8",
                        key="dl_student_csv"
                    )
                    
                with dl_col2:
                    txt_report = [
                        "=========================================",
                        "         OFFICIAL REPORT CARD            ",
                        "=========================================",
                        f"Student ID : {student_id}"
                    ]
                    if not display_df.empty and 'class' in display_df.columns:
                        txt_report.append(f"Class      : {display_df['class'].iloc[0]}")
                    txt_report.append(f"Filters    : {selected_semester} | {selected_period}")
                    txt_report.append("-----------------------------------------")
                    
                    avg_str = f"{current_avg:.2f}%" if not pd.isna(current_avg) else "N/A"
                    txt_report.append(f"Overall Filtered Average: {avg_str}\n\nSummary by Semester:")
                    for _, row in sem_avg.iterrows():
                        txt_report.append(f" - {row['semester']}: {row['grade']:.2f}%")
                    txt_report.append("\nSummary by Period:")
                    for _, row in per_avg.iterrows():
                        txt_report.append(f" - {row['period']}: {row['grade']:.2f}%")
                        
                    txt_report.append("-----------------------------------------")
                    
                    if pivot_df is not None:
                        txt_report.append("Academic Performance Matrix View:")
                        txt_report.append(pivot_df.to_string())
                    else:
                        txt_report.append(f"{'Subject':<18} | {'Semester':<10} | {'Period':<10} | {'Grade':<5}")
                        txt_report.append("-" * 53)
                        for _, row in display_df.iterrows():
                            txt_report.append(
                                f"{str(row.get('subject', '')):<18} | "
                                f"{str(row.get('semester', '')):<10} | "
                                f"{str(row.get('period', '')):<10} | "
                                f"{str(row.get('grade', '')):<5}"
                            )
                    
                    txt_report.append("=========================================")
                    txt_report.append("")
                    txt_report.append("💾 OFFICIAL VERIFICATION & AUDIT SIGN-OFF")
                    txt_report.append("-----------------------------------------")
                    txt_report.append("Principal / Administrator Signature:")
                    txt_report.append("")
                    txt_report.append("X: ______________________________________")
                    txt_report.append("")
                    txt_report.append("Institutional Stamp Area:")
                    txt_report.append("┌───────────────────────────────────────┐")
                    txt_report.append("│                                       │")
                    txt_report.append("│       OFFICIAL REGISTRAR STAMP        │")
                    txt_report.append("│                                       │")
                    txt_report.append("└───────────────────────────────────────┘")
                    txt_report.append("Date Authorized: _______________________")
                    txt_report.append("=========================================")
                    
                    txt_string = "\n".join(txt_report)
                    txt_bytes = txt_string.encode("utf-8")
                    
                    st.download_button(
                        label="📄 Download Certified Report Card (TXT)",
                        data=txt_bytes,
                        file_name=f"Certified_ReportCard_{student_id}.txt",
                        mime="text/plain; charset=utf-8",
                        key="dl_student_txt"
                    )
            else:
                st.info("💡 You are authenticated, but no grade records were found.")
        except Exception as e:
            st.error(f"❌ Error fetching student data: {str(e)}")

# --- ADMIN DASHBOARD ---
with tab_admin:
    st.header("Administrative Access Gate")
    if "admin_authenticated" not in st.session_state:
        st.session_state["admin_authenticated"] = False
        
    if not st.session_state["admin_authenticated"]:
        admin_user = st.text_input("Username:", key="admin_user_input")
        admin_pass = st.text_input("Password:", type="password", key="admin_pass_input")
        if st.button("Authenticate Admin", key="btn_admin_login"):
            if admin_user == "admin" and admin_pass == "password123":
                st.session_state["admin_authenticated"] = True
                st.rerun()
            else:
                st.error("❌ Invalid Admin Username or Password.")
    else:
        st.success("✅ Admin Authentication Successful. Live database loaded below.")
        if st.button("🚪 Logout Admin Panel", key="btn_admin_logout"):
            st.session_state["admin_authenticated"] = False
            st.rerun()
            
        st.divider()
        st.subheader("Bulk Record Upload")
        uploaded_file = st.file_uploader("Upload grades update file (.csv)", type=["csv"], key="csv_uploader")
        
        if uploaded_file is not None:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                uploaded_df.columns = [c.strip().lower() for c in uploaded_df.columns]
                
                base_required = ["id", "class", "subject", "period", "semester", "grade"]
                missing = [col for col in base_required if col not in uploaded_df.columns]
                
                if missing:
                    st.error(f"❌ Upload Rejected. Missing target columns: {', '.join(missing)}")
                else:
                    if "password_hash" not in uploaded_df.columns:
                        uploaded_df["password_hash"] = uploaded_df["id"].apply(lambda x: hash_password(str(x)))
                    
                    final_df = uploaded_df[REQUIRED_COLUMNS]
                    records = final_df.to_dict(orient="records")
                    
                    supabase.table("reportcard").insert(records).execute()
                    st.success(f"🎉 Success! Uploaded {len(records)} records to Supabase.")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Engine parsing error: {str(e)}")
                
        st.subheader("📝 Live Master Records Editor")
        st.caption("Double-click any cell to edit data or insert rows. Remember to save changes below.")
        
        try:
            master_data = supabase.table("reportcard").select("*").execute()
            master_df = pd.DataFrame(master_data.data)
            
            if not master_df.empty:
                if 'created_at' in master_df.columns:
                    master_df = master_df.drop(columns=['created_at'])
                    
                edited_df = st.data_editor(
                    master_df, 
                    use_container_width=True, 
                    num_rows="dynamic",
                    key="admin_records_editor"
                )
                
                admin_col1, admin_col2 = st.columns(2)
                
                with admin_col1:
                    if st.button("💾 Save Table Changes", key="btn_save_changes"):
                        try:
                            for index, row in edited_df.iterrows():
                                if pd.isna(row['password_hash']) or str(row['password_hash']).strip() == "":
                                    edited_df.at[index, 'password_hash'] = hash_password(str(row['id']))
                            
                            updated_records = edited_df.to_dict(orient="records")
                            
                            supabase.table("reportcard").delete().neq("id", "___TEMP_RESERVED_KEY___").execute()
                            if updated_records:
                                supabase.table("reportcard").insert(updated_records).execute()
                                
                            st.success("🎉 Database saved successfully to Supabase!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error saving database changes: {str(e)}")
                
                with admin_col2:
                    admin_csv_buffer = io.StringIO()
                    master_df.to_csv(admin_csv_buffer, index=False)
                    
                    admin_csv_bytes = admin_csv_buffer.getvalue().encode("utf-8")
                    
                    st.download_button(
                        label="📥 Download Master Database (CSV)",
                        data=admin_csv_bytes,
                        file_name="master_reportcard_database.csv",
                        mime="text/csv; charset=utf-8",
                        key="admin_download_btn"
                    )
            else:
                st.info("💡 The Supabase database table is currently empty.")
        except Exception as e:
            st.error(f"❌ Error loading master database: {str(e)}")
