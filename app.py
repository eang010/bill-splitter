import streamlit as st
import pandas as pd
import numpy as np  # Import numpy for rounding up
import os
from veryfi import Client

# Load Veryfi API credentials from Streamlit secrets
client_id = st.secrets['veryfi']['client_id']
client_secret = st.secrets['veryfi']['client_secret']
username = st.secrets['veryfi']['username']
api_key = st.secrets['veryfi']['api_key']

# Initialize session state for names and processed data
if 'names' not in st.session_state:
    st.session_state.names = ['Alvin', 'Clement', 'Emily', 'James',
                              'Kian Ping', 'Sean', 'Shawn', 'Stepfenny']
if 'orders_df' not in st.session_state:
    st.session_state.orders_df = pd.DataFrame(
        columns=['Order Description', 'Amount', 'Assigned Name'])

# Sidebar for adding and deleting names
st.sidebar.header("Manage Names")

# Input form to add new names
with st.sidebar.form("add_name_form"):
    new_name = st.text_input("Add a new name:")
    add_button = st.form_submit_button("Add Name")
    if add_button:
        if new_name and new_name not in st.session_state.names:
            st.session_state.names.append(new_name)
            st.sidebar.success(f'Added name: {new_name}')
        elif new_name in st.session_state.names:
            st.sidebar.warning(f'Name "{new_name}" already exists.')

# Dropdown to delete names, show empty field unless a name is selected
name_to_delete = st.sidebar.selectbox(
    "Delete a name:", options=[''] + st.session_state.names if st.session_state.names else [''])
if st.sidebar.button("Delete Name"):
    if name_to_delete in st.session_state.names:
        st.session_state.names.remove(name_to_delete)
        st.sidebar.success(f'Deleted name: {name_to_delete}')

# File uploader for receipt files
st.sidebar.header("Upload Receipt")
uploaded_file = st.sidebar.file_uploader(
    "Choose a receipt file", type=["jpg", "jpeg", "png"])

if uploaded_file is not None and 'processed' not in st.session_state:
    # Save the uploaded file to a temporary location
    file_path = f"/tmp/{uploaded_file.name}"
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Process the uploaded document with Veryfi
    veryfi_client = Client(client_id, client_secret, username, api_key)
    categories = ['Lunch']  # You can adjust categories as needed
    response = veryfi_client.process_document(file_path, categories=categories)

    # Extract the line items from the response
    line_items = response.get('line_items', [])

    # Filter and extract the order description and amount for each item
    orders = [(item.get('description', 'N/A'), item.get('total', 0))
              for item in line_items]

    # Create a DataFrame to store the line items and initialize 'Assigned Name'
    st.session_state.orders_df = pd.DataFrame(
        orders, columns=['Order Description', 'Amount'])
    # Initialize 'Assigned Name' column
    st.session_state.orders_df['Assigned Name'] = ''
    st.session_state.processed = True  # Mark receipt as processed

# Reference orders_df from the session state
orders_df = st.session_state.orders_df

st.title("Bill Splitter App")

# Add an expander for assigning names and editing amounts
with st.expander("Assign Names and Edit Amounts"):
    for i, row in orders_df.iterrows():
        st.write(f"Item: {row['Order Description']}")
        cols = st.columns([3, 2])  # Adjust column widths

        with cols[0]:  # First column for name assignment
            selected_name = st.selectbox(f"Name:", options=[
                                         ''] + st.session_state.names, key=f'name_{i}')
            # Update 'Assigned Name'
            orders_df.at[i, 'Assigned Name'] = selected_name

        with cols[1]:  # Second column for editable amount
            item_amount = st.number_input(
                f"Amount:",
                value=row['Amount'],
                min_value=0.0,
                format="%.2f",
                key=f'amount_{i}'
            )
            # Update the total amount in DataFrame
            orders_df.at[i, 'Amount'] = item_amount

# Input fields for service charge and GST rates
st.sidebar.header("Rates")
service_charge_enabled = st.sidebar.checkbox(
    "Enable Service Charge", value=True)
service_charge_rate = st.sidebar.number_input(
    "Service Charge Rate (%)", min_value=0.0, max_value=100.0, value=10.0 if service_charge_enabled else 0.0)
gst_enabled = st.sidebar.checkbox("Enable GST", value=True)
gst_rate = st.sidebar.number_input(
    "GST Rate (%)", min_value=0.0, max_value=100.0, value=9.0 if gst_enabled else 0.0)

# Create new columns for service charge and GST
orders_df['Service Charge'] = orders_df['Amount'] * \
    (service_charge_rate / 100) if service_charge_enabled else 0.0
orders_df['GST'] = (orders_df['Amount'] + orders_df['Service Charge']
                    ) * (gst_rate / 100) if gst_enabled else 0.0

# Calculate final amount for each item (before rounding)
orders_df['Final Amount (Unrounded)'] = orders_df['Amount'] + \
    orders_df['Service Charge'] + orders_df['GST']

# Ensure the 'Assigned Name' column exists before grouping
if 'Assigned Name' in orders_df.columns:
    # Group by 'Assigned Name' and sum the amounts
    grouped_df = orders_df.groupby('Assigned Name').agg(
        Total_Orders=('Amount', 'sum'),
        Total_Service_Charge=('Service Charge', 'sum'),
        Total_GST=('GST', 'sum'),
        # Use unrounded for overall total
        Final_Amount=('Final Amount (Unrounded)', 'sum')
    ).reset_index()
else:
    st.warning("The 'Assigned Name' column is missing in the orders DataFrame.")
    grouped_df = pd.DataFrame(columns=[
                              'Assigned Name', 'Total_Orders', 'Total_Service_Charge', 'Total_GST', 'Final_Amount'])

# Calculate overall totals based on unrounded values
overall_totals = pd.DataFrame({
    'Assigned Name': ['Overall Total'],
    'Total_Orders': [grouped_df['Total_Orders'].sum()],
    'Total_Service_Charge': [grouped_df['Total_Service_Charge'].sum()],
    'Total_GST': [grouped_df['Total_GST'].sum()],
    # Round up overall final amount
    'Final_Amount': [np.ceil(grouped_df['Final_Amount'].sum() * 100) / 100]
})

# Concatenate the overall totals with the grouped DataFrame
final_grouped_df = pd.concat([grouped_df, overall_totals], ignore_index=True)

# Round individual final amounts to 2 decimal places for display in summary table
final_grouped_df['Final_Amount'] = np.ceil(
    final_grouped_df['Final_Amount'] * 100) / 100  # Round up for display

# Display the final grouped table
st.write("### Final Summary")
st.dataframe(final_grouped_df)

# Optional: Display individual item details
if st.checkbox("Show Individual Item Details"):
    st.write("### Individual Order Details")
    # Keep unrounded values for individual details
    orders_df['Final Amount'] = orders_df['Final Amount (Unrounded)']
    st.dataframe(orders_df[['Assigned Name', 'Order Description',
                            'Amount', 'Service Charge', 'GST', 'Final Amount']])
