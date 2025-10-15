# ============================================================
# STREAMLIT BACK ORDER MANAGEMENT APP - FAST VERSION
# Save this as: app.py
# Run with: streamlit run app.py
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

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
    
    # Clean customer names
    df['Sell-to Customer Name'] = df['Sell-to Customer Name'].astype(str).str.strip()
    df = df[df['Sell-to Customer Name'] != '']
    df = df[df['Sell-to Customer Name'] != 'nan']
    df = df[df['Sell-to Customer Name'] != 'NaN']
    df = df[~df['Sell-to Customer Name'].str.isdigit()]
    
    # Remove missing data
    df_clean = df.dropna(subset=['QOH', 'Sell-to Customer Name', 
                                   'Outstanding Amount', 'Mfg. Lead Name'])
    
    return df_clean

# ============================================================
# INITIALIZE SESSION STATE
# ============================================================

if 'file_uploaded' not in st.session_state:
    st.session_state.file_uploaded = False

# ============================================================
# HEADER
# ============================================================

st.title("📦 Back Order Management Dashboard")
st.markdown("*Fast, simple back order tracking by customer*")

st.markdown("---")

# ============================================================
# SIDEBAR - FILE UPLOAD
# ============================================================

with st.sidebar:
    st.header("📁 Upload Data")
    uploaded_file = st.file_uploader(
        "Upload Excel or CSV file",
        type=['xlsx', 'csv', 'xls'],
        help="Upload your ELS Global Back Order file"
    )
    
    if uploaded_file is not None:
        st.session_state.file_uploaded = True
        st.success("✅ File loaded!")
    
    st.divider()
    st.info(
        """
        **Features:**
        - View by customer
        - Filter by stock status
        - Export to Excel/CSV
        - Fast performance
        """
    )

# ============================================================
# MAIN CONTENT
# ============================================================

if uploaded_file is not None:
    
    try:
        # Load and cache data
        file_bytes = uploaded_file.read()
        df_clean = load_and_clean_data(file_bytes, uploaded_file.name)
        
        # Separate back orders and in-stock
        backorders = df_clean[df_clean['QOH'] == 0]
        instock = df_clean[df_clean['QOH'] > 0]
        
        # ============================================================
        # SUMMARY METRICS
        # ============================================================
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Back Order Items",
                len(backorders),
                f"{(len(backorders)/len(df_clean)*100):.1f}%"
            )
        
        with col2:
            st.metric(
                "Back Order Value",
                f"${backorders['Outstanding Amount'].sum():,.0f}"
            )
        
        with col3:
            st.metric(
                "In-Stock Value",
                f"${instock['Outstanding Amount'].sum():,.0f}"
            )
        
        with col4:
            st.metric(
                "Unique Customers",
                df_clean['Sell-to Customer Name'].nunique()
            )
        
        st.markdown("---")
        
        # ============================================================
        # FILTERS
        # ============================================================
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            stock_filter = st.selectbox(
                "Stock Status",
                ["All", "Back Order Only", "In Stock Only"]
            )
        
        with col2:
            customer_min = st.number_input(
                "Customer Min. Total $",
                min_value=0,
                value=0,
                step=500
            )
        
        with col3:
            customer_max = st.number_input(
                "Customer Max. Total $",
                min_value=0,
                value=1000000,
                step=1000
            )
        
        # Apply stock filter
        if stock_filter == "Back Order Only":
            filtered_df = backorders.copy()
        elif stock_filter == "In Stock Only":
            filtered_df = instock.copy()
        else:
            filtered_df = df_clean.copy()
        
        # Calculate customer totals
        customer_totals = filtered_df.groupby('Sell-to Customer Name')['Outstanding Amount'].sum()
        valid_customers = customer_totals[
            (customer_totals >= customer_min) & 
            (customer_totals <= customer_max)
        ].index.tolist()
        
        filtered_df = filtered_df[filtered_df['Sell-to Customer Name'].isin(valid_customers)]
        
        st.markdown("---")
        
        # ============================================================
        # CUSTOMER TABLE VIEW
        # ============================================================
        
        if len(filtered_df) > 0:
            
            st.subheader(f"📊 Orders by Customer ({len(valid_customers)} customers)")
            
            # Customer summary table
            customer_summary = filtered_df.groupby('Sell-to Customer Name').agg({
                'Outstanding Amount': 'sum',
                'QOH': lambda x: (x == 0).sum(),
                'Sales Order No': 'count'
            }).reset_index()
            
            customer_summary.columns = ['Customer', 'Total Outstanding', 'Back Order Items', 'Total Items']
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
                
                # Customer metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Outstanding", f"${customer_df['Outstanding Amount'].sum():,.2f}")
                with col2:
                    st.metric("Total Items", len(customer_df))
                with col3:
                    st.metric("Back Orders", len(customer_df[customer_df['QOH'] == 0]))
                with col4:
                    st.metric("In Stock", len(customer_df[customer_df['QOH'] > 0]))
                
                st.markdown("---")
                
                # Orders table
                display_df = customer_df[[
                    'Sales Order No',
                    'Item No',
                    'Desc',
                    'Outstanding Amount',
                    'QOH',
                    'Requested Delivery Date',
                    'Mfg. Lead Name'
                ]].copy()
                
                display_df.columns = [
                    'Order #',
                    'Item #',
                    'Description',
                    'Outstanding $',
                    'QOH',
                    'Delivery Date',
                    'Mfg Lead'
                ]
                
                # Add status column
                display_df['Status'] = display_df['QOH'].apply(
                    lambda x: '🔴 BACK ORDER' if x == 0 else '🟢 IN STOCK'
                )
                
                # Format currency
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
            # CSV export
            csv_data = filtered_df.to_csv(index=False)
            st.download_button(
                label="📄 Download as CSV",
                data=csv_data,
                file_name=f"back_orders_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        with col2:
            # Excel export
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
            # Customer summary export
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

else:
    st.info(
        """
        👈 **Getting Started:**
        
        1. Upload your back order file (Excel or CSV) using the sidebar
        2. View summary metrics and filter by customer value
        3. Select a customer to see detailed orders
        4. Export data as needed
        
        **Required columns:**
        - QOH (Quantity on Hand)
        - Sell-to Customer Name
        - Outstanding Amount
        - Mfg. Lead Name
        - Sales Order No
        - Item No
        - Desc
        - Requested Delivery Date
        """
    )
