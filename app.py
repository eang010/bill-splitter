import streamlit as st
import pandas as pd
import numpy as np
import os
from veryfi import Client
from utility import check_password

# Check password and disclaimer
if not check_password():
    st.stop()

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
        columns=['Order Description', 'Amount', 'Assigned Names'])

st.sidebar.title("🤑 Bill Splitter App")

st.sidebar.divider()

# Sidebar for adding and deleting names
st.sidebar.header("👤 Manage Names")

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

st.sidebar.divider()

# Sidebar for service charge and GST settings
st.sidebar.header("💱 Taxes")
service_charge_enabled = st.sidebar.checkbox(
    "Enable Service Charge", value=True)
service_charge_rate = st.sidebar.number_input(
    "Service Charge Rate (%)", min_value=0.0, max_value=100.0, value=10.0 if service_charge_enabled else 0.0)
gst_enabled = st.sidebar.checkbox("Enable GST", value=True)
gst_rate = st.sidebar.number_input(
    "GST Rate (%)", min_value=0.0, max_value=100.0, value=9.0 if gst_enabled else 0.0)


st.sidebar.divider()

# Sidebar section to add the discount for the entire bill
st.sidebar.header("💸 Discount")
total_discount = st.sidebar.number_input(
    "Total Discount:",
    value=0.0,
    min_value=0.0,
    format="%.2f"
)

discount_application = st.sidebar.radio(
    "Apply Discount:",
    options=["Before GST and Service Charge", "After GST and Service Charge"],
    index=0  # Default selection to "Before GST and Service Charge"
)

st.sidebar.divider()

# File uploader for receipt files
st.sidebar.header("🧾 Upload Receipt")
uploaded_file = st.sidebar.file_uploader(
    "Choose a receipt file", type=["jpg", "jpeg", "png"])

if uploaded_file is not None and 'processed' not in st.session_state:
    file_path = f"/tmp/{uploaded_file.name}"
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    veryfi_client = Client(client_id, client_secret, username, api_key)
    categories = ['Lunch']
    response = veryfi_client.process_document(file_path, categories=categories)

    line_items = response.get('line_items', [])
    orders = [(item.get('description', 'N/A'), item.get('total', 0))
              for item in line_items]

    st.session_state.orders_df = pd.DataFrame(
        orders, columns=['Order Description', 'Amount'])
    st.session_state.orders_df['Assigned Names'] = [[]
                                                    for _ in range(len(orders))]
    st.session_state.processed = True

orders_df = st.session_state.orders_df

st.title("Bill Splitter App")

if not orders_df.empty:
    with st.expander("Assign Names and Edit Amounts"):
        for i, row in orders_df.iterrows():
            st.write(f"Item: {row['Order Description']}")
            cols = st.columns([3, 2])

            with cols[0]:
                selected_names = st.multiselect(
                    f"Assign Names to Item:", options=st.session_state.names, key=f'names_{i}')
                orders_df.at[i, 'Assigned Names'] = selected_names

            with cols[1]:
                item_amount = st.number_input(
                    f"Amount:", value=row['Amount'], min_value=0.0, format="%.2f", key=f'amount_{i}')
                orders_df.at[i, 'Amount'] = item_amount

    orders_df['Split Amount'] = orders_df.apply(
        lambda row: row['Amount'] / len(row['Assigned Names']) if len(row['Assigned Names']) > 0 else 0, axis=1)

    expanded_rows = []
    for _, row in orders_df.iterrows():
        if len(row['Assigned Names']) > 0:
            for name in row['Assigned Names']:
                expanded_rows.append({
                    'Assigned Name': name,
                    'Order Description': row['Order Description'],
                    'Amount': row['Split Amount']
                })

    expanded_df = pd.DataFrame(expanded_rows)

    if not expanded_df.empty:
        overall_total = expanded_df['Amount'].sum()
        discount_amount = total_discount if discount_application == "Before GST and Service Charge" else 0
        subtotal_after_discount = overall_total - discount_amount

        service_charge = subtotal_after_discount * \
            (service_charge_rate / 100) if service_charge_enabled else 0.0
        gst = (subtotal_after_discount + service_charge) * \
            (gst_rate / 100) if gst_enabled else 0.0

        final_total = subtotal_after_discount + service_charge + gst
        final_total_after_discount = final_total - \
            (total_discount if discount_application ==
             "After GST and Service Charge" else 0)

        # Calculate the number of unique participants
        num_participants = len(expanded_df['Assigned Name'].unique())

        # Calculate the even discount per participant
        even_discount_per_person = total_discount / num_participants if num_participants > 0 else 0

        # Apply the even discount to each person's final amount
        expanded_df['Proportionate Discount'] = even_discount_per_person
        expanded_df['Service Charge'] = expanded_df['Amount'] * \
            (service_charge_rate / 100) if service_charge_enabled else 0.0
        expanded_df['GST'] = (expanded_df['Amount'] + expanded_df['Service Charge']
                              ) * (gst_rate / 100) if gst_enabled else 0.0
        expanded_df['Final Amount'] = expanded_df['Amount'] - \
            expanded_df['Proportionate Discount'] + \
                expanded_df['Service Charge'] + \
                    expanded_df['GST']
                                              

        # Group the data by 'Assigned Name' and summarize the totals for each person
        summary_data = expanded_df.groupby('Assigned Name').agg(
            Total_Orders=('Amount', 'sum'),
            Total_Discount=('Proportionate Discount', 'sum'),
            Total_Service_Charge=('Service Charge', 'sum'),
            Total_GST=('GST', 'sum'),
            Final_Amount=('Final Amount', 'sum')
        ).reset_index()

        # Append the overall total row to the summary data
        overall_summary = pd.DataFrame({
            'Assigned Name': ['Overall Total'],
            'Total_Orders': [overall_total],
            'Total_Discount': [total_discount],
            'Total_Service_Charge': [service_charge],
            'Total_GST': [gst],
            'Final_Amount': [final_total_after_discount]  # No rounding
        })

        summary_data = pd.concat(
            [summary_data, overall_summary], ignore_index=True)

        with st.expander("Overall Bill Summary"):
            st.write("### Overall Bill Summary")
            st.dataframe(summary_data)

        with st.expander("Final Summary for Each Assigned Name"):
            st.write("### Final Summary Breakdown for Each Assigned Name")
            sorted_expanded_df = expanded_df.sort_values(by='Assigned Name')
            st.dataframe(sorted_expanded_df[['Assigned Name', 'Order Description', 'Amount',
                         'Proportionate Discount', 'Service Charge', 'GST', 'Final Amount']])

        # New table to show only Assigned Name and Final Amount
        final_summary_table = summary_data[['Assigned Name', 'Final_Amount']]
        # Round the Final Amount for display in the summary table
        final_summary_table['Final_Amount'] = final_summary_table['Final_Amount'].round(
            2)
        st.write("### Summary of Final Amounts by Assigned Name")
        st.dataframe(final_summary_table)

else:
    st.info('Please upload a receipt to get started.', icon="💡")


st.sidebar.divider()
st.sidebar.code(
    "Laziness 🔉 \n[ley-zee-nis] \n\nnoun \nThe secret ingredient\nof innovation! \n\nBy Emily ♥")
