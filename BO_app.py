# ============================================================
# STREAMLIT BACK ORDER MANAGEMENT APP - ENHANCED FINAL VERSION
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

import hmac

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    # Return True if password is validated
    if st.session_state.get("password_correct", False):
        return True

    # Show password input
    st.text_input(
        "🔐 Enter Password", 
        type="password", 
        on_change=password_entered, 
        key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False

if not check_password():
    st.stop()  # Don't continue if password is incorrect
# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Back Order Management",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CACHING FOR PERFORMANCE
# ============================================================

@st.cache_data
def load_and_clean_data(file_bytes, file_name):
    """Load and clean data with caching"""
    if file_name.endswith('.xlsx') or file_name.endswith('.xls'):
        df = pd.read_excel(io.BytesIO(file_bytes))
    else:
        df = pd.read_csv(io.BytesIO(file_bytes))
    
    # Convert to numeric
    df['QOH'] = pd.to_numeric(df['QOH'], errors='coerce')
    df['Outstanding Amount'] = pd.to_numeric(df['Outstanding Amount'], errors='coerce')
    
    # Convert Outstanding Quantity if it exists
    if 'Outstanding Quantity' in df.columns:
        df['Outstanding Quantity'] = pd.to_numeric(df['Outstanding Quantity'], errors='coerce')
    
    # Clean customer names
    df['Sell-to Customer Name'] = df['Sell-to Customer Name'].astype(str).str.strip()
    df = df[df['Sell-to Customer Name'] != '']
    df = df[df['Sell-to Customer Name'].notna()]
    df = df[~df['Sell-to Customer Name'].str.isdigit()]
    
    # Clean date column if present
    if 'Requested Delivery Date' in df.columns:
        df['Requested Delivery Date'] = pd.to_datetime(df['Requested Delivery Date'], errors='coerce')

    # Remove missing key data
    df_clean = df.dropna(subset=[
        'QOH', 'Sell-to Customer Name', 'Outstanding Amount', 'Mfg. Lead Name'
    ])
    
    # Calculate shortage if Outstanding Quantity exists
    if 'Outstanding Quantity' in df_clean.columns:
        df_clean['Shortage Qty'] = df_clean.apply(
            lambda row: max(0, row['Outstanding Quantity'] - row['QOH']) if pd.notna(row['Outstanding Quantity']) else 0,
            axis=1
        )
        df_clean['Can Fulfill'] = df_clean.apply(
            lambda row: row['QOH'] >= row['Outstanding Quantity'] if pd.notna(row['Outstanding Quantity']) else row['QOH'] > 0,
            axis=1
        )
    
    return df_clean

# ============================================================
# HEADER
# ============================================================

st.title("📦 Back Order Management Dashboard")
st.markdown("*Fast back order tracking with smart shortage detection*")
st.markdown("---")

# ============================================================
# SIDEBAR - FILE UPLOAD + SETTINGS
# ============================================================

with st.sidebar:
    st.header("📁 Upload Data")
    uploaded_file = st.file_uploader(
        "Upload Excel or CSV file",
        type=['xlsx', 'csv', 'xls'],
        help="Upload your ELS Global Back Order file"
    )
    
    st.divider()
    st.header("⚙️ Settings")
    
    # Back Order Logic Selection
    backorder_logic = st.radio(
        "Back Order Definition:",
        ["Strict (QOH = 0 only)", "Smart (QOH < Order Quantity)"],
        help="Strict: Only items with zero stock. Smart: Items with insufficient stock to fulfill order."
    )

    future_weeks = st.slider(
        "Define 'Future Orders' cutoff (weeks from today)",
        min_value=1,
        max_value=12,
        value=3,
        help="Orders with Requested Delivery Date later than this many weeks from today."
    )
    
    st.divider()
    
    # Dynamic info based on mode
    if backorder_logic == "Smart (QOH < Order Quantity)":
        st.success("""
        **Smart Mode Active** ✨
        - Detects partial shortages
        - Example: QOH=10, Need=100 → Back Order
        """)
    else:
        st.info("""
        **Strict Mode Active**
        - Only QOH = 0 items
        - Example: QOH=10, Need=100 → NOT Back Order
        """)

# ============================================================
# MAIN CONTENT
# ============================================================

if uploaded_file is not None:
    try:
        file_bytes = uploaded_file.read()
        df_clean = load_and_clean_data(file_bytes, uploaded_file.name)
        
        # Check if Outstanding Quantity column exists
        has_outstanding_qty = 'Outstanding Quantity' in df_clean.columns
        
        # Determine back orders based on selected logic
        if backorder_logic == "Strict (QOH = 0 only)":
            # Original logic: Only QOH = 0
            backorders = df_clean[df_clean['QOH'] == 0]
            instock = df_clean[df_clean['QOH'] > 0]
        else:
            # Smart logic: QOH < Outstanding Quantity
            if has_outstanding_qty:
                backorders = df_clean[
                    (df_clean['Outstanding Quantity'].notna()) &
                    (df_clean['QOH'] < df_clean['Outstanding Quantity'])
                ]
                instock = df_clean[
                    (df_clean['Outstanding Quantity'].notna()) &
                    (df_clean['QOH'] >= df_clean['Outstanding Quantity'])
                ]
            else:
                # Fallback to strict if column doesn't exist
                st.warning("⚠️ 'Outstanding Quantity' column not found. Using Strict logic (QOH=0).")
                backorders = df_clean[df_clean['QOH'] == 0]
                instock = df_clean[df_clean['QOH'] > 0]
        
        # Separate categories for smart mode
        full_backorders = df_clean[df_clean['QOH'] == 0]
        if has_outstanding_qty:
            partial_backorders = df_clean[
                (df_clean['QOH'] > 0) & 
                (df_clean['Outstanding Quantity'].notna()) &
                (df_clean['QOH'] < df_clean['Outstanding Quantity'])
            ]
        else:
            partial_backorders = pd.DataFrame()
        
        # Future orders
        today = datetime.today()
        cutoff_date = today + timedelta(weeks=future_weeks)
        future_orders = df_clean[
            (df_clean['Requested Delivery Date'].notna()) &
            (df_clean['Requested Delivery Date'] >= cutoff_date)
        ]
        
        # ============================================================
        # SUMMARY METRICS
        # ============================================================

        if backorder_logic == "Smart (QOH < Order Quantity)" and has_outstanding_qty:
            # Enhanced metrics for smart mode
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Back Order Items", len(backorders),
                          f"{(len(backorders) / len(df_clean) * 100):.1f}%")
            with col2:
                st.metric("Full Back Orders", len(full_backorders),
                          delta="QOH = 0")
            with col3:
                st.metric("Partial Shortages", len(partial_backorders),
                          delta="QOH < Needed")
            with col4:
                st.metric("Back Order Value",
                          f"${backorders['Outstanding Amount'].sum():,.0f}")
            with col5:
                st.metric("Can Fulfill",
                          f"${instock['Outstanding Amount'].sum():,.0f}")
        else:
            # Standard metrics for strict mode
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Back Order Items", len(backorders),
                          f"{(len(backorders) / len(df_clean) * 100):.1f}%")
            with col2:
                st.metric("Back Order Value",
                          f"${backorders['Outstanding Amount'].sum():,.0f}")
            with col3:
                st.metric("In-Stock Value",
                          f"${instock['Outstanding Amount'].sum():,.0f}")
            with col4:
                st.metric("Unique Customers",
                          df_clean['Sell-to Customer Name'].nunique())
        
        st.markdown("---")
        
        # ============================================================
        # FILTERS
        # ============================================================

        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Dynamic filter options based on mode
            if backorder_logic == "Smart (QOH < Order Quantity)" and has_outstanding_qty:
                filter_options = ["All", "Back Order Only", "Full Back Order (QOH=0)", 
                                 "Partial Shortage", "Can Fulfill", "Future Orders"]
            else:
                filter_options = ["All", "Back Order Only", "In Stock Only", "Future Orders"]
            
            stock_filter = st.selectbox("Stock Status", filter_options)
        
        with col2:
            customer_min = st.number_input(
                "Customer Min. Total $", min_value=0, value=0, step=500
            )
        
        with col3:
            customer_max = st.number_input(
                "Customer Max. Total $", min_value=0, value=1000000, step=1000
            )
        
        # Apply stock filter
        if stock_filter == "Back Order Only":
            filtered_df = backorders.copy()
        elif stock_filter == "Full Back Order (QOH=0)":
            filtered_df = full_backorders.copy()
        elif stock_filter == "Partial Shortage":
            filtered_df = partial_backorders.copy()
        elif stock_filter == "Can Fulfill":
            filtered_df = instock.copy()
        elif stock_filter == "In Stock Only":
            filtered_df = instock.copy()
        elif stock_filter == "Future Orders":
            filtered_df = future_orders.copy()
        else:
            filtered_df = df_clean.copy()
        
        # Filter by customer totals
        customer_totals = filtered_df.groupby('Sell-to Customer Name')['Outstanding Amount'].sum()
        valid_customers = customer_totals[
            (customer_totals >= customer_min) & (customer_totals <= customer_max)
        ].index.tolist()
        filtered_df = filtered_df[filtered_df['Sell-to Customer Name'].isin(valid_customers)]
        
        # Explanation expander
        with st.expander("ℹ️ Understanding Back Order Logic"):
            if backorder_logic == "Strict (QOH = 0 only)":
                st.write("**Current Mode: STRICT** 🔒")
                st.write("- Back Order = QOH equals 0 (completely out of stock)")
                st.write("- Example: QOH=10, Need=100 → **NOT** a back order")
                st.write("- Use this if you only care about items with zero stock")
            else:
                st.write("**Current Mode: SMART** 🧠")
                st.write("- Back Order = QOH < Outstanding Quantity (insufficient stock)")
                st.write("- Example: QOH=10, Need=100 → **IS** a back order (shortage of 90)")
                st.write("")
                st.write("**Categories:**")
                st.write("- 🔴 Full Back Order: QOH = 0 (no stock at all)")
                st.write("- 🟡 Partial Shortage: QOH > 0 but < Needed (some stock, not enough)")
                st.write("- 🟢 Can Fulfill: QOH >= Needed (sufficient stock)")
        
        st.markdown("---")
        
        # ============================================================
        # CUSTOMER TABLE VIEW
        # ============================================================

        if len(filtered_df) > 0:
            st.subheader(f"📊 Orders by Customer ({len(valid_customers)} customers)")
            
            # Build aggregation based on available columns
            agg_dict = {
                'Outstanding Amount': 'sum',
                'QOH': lambda x: (x == 0).sum(),
                'Sales Order No': 'count'
            }
            
            if 'Shortage Qty' in filtered_df.columns:
                agg_dict['Shortage Qty'] = 'sum'
            
            customer_summary = filtered_df.groupby('Sell-to Customer Name').agg(agg_dict).reset_index()
            
            # Rename columns
            col_names = ['Customer', 'Total Outstanding', 'Full Back Orders', 'Total Items']
            if 'Shortage Qty' in filtered_df.columns:
                col_names.insert(3, 'Total Shortage Qty')
            
            customer_summary.columns = col_names
            customer_summary = customer_summary.sort_values('Total Outstanding', ascending=False)
            customer_summary['Total Outstanding'] = customer_summary['Total Outstanding'].apply(lambda x: f"${x:,.2f}")
            
            st.dataframe(customer_summary, use_container_width=True, hide_index=True)
            st.markdown("---")
            
            # ============================================================
            # DETAILED VIEW - SELECTED CUSTOMER
            # ============================================================

            st.subheader("🔍 Customer Detail View")
            
            selected_customer = st.selectbox(
                "Select a customer to view details:",
                valid_customers,
                key="customer_selector"
            )
            
            if selected_customer:
                customer_df = filtered_df[filtered_df['Sell-to Customer Name'] == selected_customer]
                
                # Metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Outstanding", f"${customer_df['Outstanding Amount'].sum():,.2f}")
                with col2:
                    st.metric("Total Items", len(customer_df))
                with col3:
                    st.metric("Full Back Orders", len(customer_df[customer_df['QOH'] == 0]))
                with col4:
                    if 'Shortage Qty' in customer_df.columns:
                        total_shortage = customer_df['Shortage Qty'].sum()
                        st.metric("Total Shortage Units", f"{int(total_shortage)}")
                    else:
                        st.metric("In Stock", len(customer_df[customer_df['QOH'] > 0]))
                
                st.markdown("---")
                
                # Build display dataframe
                display_cols = ['Sales Order No', 'Item No', 'Desc', 'Outstanding Amount', 'QOH']
                
                if 'Outstanding Quantity' in customer_df.columns:
                    display_cols.append('Outstanding Quantity')
                if 'Shortage Qty' in customer_df.columns:
                    display_cols.append('Shortage Qty')
                
                display_cols.extend(['Requested Delivery Date', 'Mfg. Lead Name'])
                
                display_df = customer_df[display_cols].copy()
                
                # Rename columns
                col_rename = {
                    'Sales Order No': 'Order #',
                    'Item No': 'Item #',
                    'Desc': 'Description',
                    'Outstanding Amount': 'Outstanding $',
                    'Outstanding Quantity': 'Qty Needed',
                    'Shortage Qty': 'Shortage',
                    'Requested Delivery Date': 'Delivery Date',
                    'Mfg. Lead Name': 'Mfg Lead'
                }
                display_df.columns = [col_rename.get(c, c) for c in display_df.columns]
                
                # Add status column
                if 'Qty Needed' in display_df.columns and backorder_logic == "Smart (QOH < Order Quantity)":
                    display_df['Status'] = display_df.apply(
                        lambda row: '🔴 FULL BACK ORDER' if row['QOH'] == 0 
                        else ('🟡 PARTIAL SHORTAGE' if pd.notna(row.get('Qty Needed')) and row['QOH'] < row['Qty Needed']
                        else '🟢 CAN FULFILL'),
                        axis=1
                    )
                else:
                    display_df['Status'] = display_df['QOH'].apply(
                        lambda x: '🔴 BACK ORDER' if x == 0 else '🟢 IN STOCK'
                    )
                
                display_df['Outstanding $'] = display_df['Outstanding $'].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        else:
            st.info("No customers match your filters. Adjust filter settings above.")
        
        st.markdown("---")
        
        # ============================================================
        # EXPORT OPTIONS
        # ============================================================

        st.subheader("📥 Export Data")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            csv_data = filtered_df.to_csv(index=False)
            st.download_button(
                label="📄 Download as CSV",
                data=csv_data,
                file_name=f"back_orders_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        with col2:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Back Orders')
            output.seek(0)
            st.download_button(
                label="📊 Download as Excel",
                data=output,
                file_name=f"back_orders_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        with col3:
            csv_summary = customer_summary.to_csv(index=False)
            st.download_button(
                label="📋 Download Summary",
                data=csv_summary,
                file_name=f"customer_summary_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.write("Please ensure your file has these columns:")
        st.write("- QOH, Sell-to Customer Name, Outstanding Amount, Mfg. Lead Name")
        st.write("- Outstanding Quantity (optional, for Smart mode)")

else:
    st.info(
        """
        👈 **Getting Started:**
        1. Upload your back order file (Excel or CSV)  
        2. Choose back order logic:
           - **Strict**: Only QOH = 0 items
           - **Smart**: QOH < Order Quantity (detects partial shortages)
        3. Adjust future order cutoff if needed
        4. Explore and export data  

        **Required columns:**  
        - QOH (Quantity on Hand)  
        - Sell-to Customer Name  
        - Outstanding Amount  
        - Mfg. Lead Name  
        - Outstanding Quantity (optional, enables Smart mode)
        - Sales Order No  
        - Item No  
        - Desc  
        - Requested Delivery Date  
        """
    )
