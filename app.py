import streamlit as st
import pandas as pd

# Sample response from the Veryfi API (your actual response might be different)
response = {
    'line_items': [
        {'description': '1K16 SALMON BELLY DON', 'total': 17.9},
        {'description': '04 EBI MENTAIYAKI UDON', 'total': 16.9},
        {'description': 'K1 KEI SIGNATURE KAISENDON SMALL', 'total': 14.9},
        {'description': 'SET G SEAFOOD CHAWANMUSHI & GREE', 'total': 5.9},
        {'description': 'UZ TORI TERIYAKI UDON', 'total': 14.9},
        {'description': 'K4 MENTAIYAKI TAMAGO KAISENDON', 'total': 20.9},
    ]
}

# Initialize a session state for names
if 'names' not in st.session_state:
    st.session_state.names = ['Alvin', 'Clement', 'Emily', 'James',
                              'Kian Ping', 'Sean', 'Shawn', 'Stepfenny']

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

# Dropdown to delete names
name_to_delete = st.sidebar.selectbox(
    "Delete a name:", options=st.session_state.names)
if st.sidebar.button("Delete Name"):
    if name_to_delete in st.session_state.names:
        st.session_state.names.remove(name_to_delete)
        st.sidebar.success(f'Deleted name: {name_to_delete}')

# Create a DataFrame to store the line items
orders_df = pd.DataFrame(response['line_items'])

# Create a new column to assign names to each order
orders_df['Assigned Name'] = None

st.title("Bill Splitter App")

# Loop through each item and create a selectbox to assign names
for i, row in orders_df.iterrows():
    selected_name = st.selectbox(f"Assign a name to: {row['description']}", options=[
                                 ''] + st.session_state.names, key=f'name_{i}')
    orders_df.at[i, 'Assigned Name'] = selected_name

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
if service_charge_enabled:
    orders_df['Service Charge'] = orders_df['total'] * \
        (service_charge_rate / 100)
else:
    orders_df['Service Charge'] = 0.0

# Conditional GST calculation based on user input
if gst_enabled:
    orders_df['GST'] = (orders_df['total'] +
                        orders_df['Service Charge']) * (gst_rate / 100)
else:
    orders_df['GST'] = 0.0

# Calculate final amount for each item
orders_df['Final Amount'] = orders_df['total'] + \
    orders_df['Service Charge'] + orders_df['GST']

# Group by 'Assigned Name' and sum the amounts
grouped_df = orders_df.groupby('Assigned Name').agg(
    Total_Orders=('total', 'sum'),
    Total_Service_Charge=('Service Charge', 'sum'),
    Total_GST=('GST', 'sum'),
    Final_Amount=('Final Amount', 'sum')
).reset_index()

# Round totals to 2 decimal places
grouped_df = grouped_df.round(2)

# Calculate overall totals
overall_totals = pd.DataFrame({
    'Assigned Name': ['Overall Total'],
    'Total_Orders': [grouped_df['Total_Orders'].sum()],
    'Total_Service_Charge': [grouped_df['Total_Service_Charge'].sum()],
    'Total_GST': [grouped_df['Total_GST'].sum()],
    'Final_Amount': [grouped_df['Final_Amount'].sum()]
})

# Concatenate the overall totals with the grouped DataFrame
final_grouped_df = pd.concat([grouped_df, overall_totals], ignore_index=True)

# Display the updated table
st.write("### Order Summary by Assigned Names")
st.dataframe(final_grouped_df)

# Optional: Display individual item details
if st.checkbox("Show Individual Item Details"):
    st.write("### Individual Order Details")
    st.dataframe(orders_df[['Assigned Name', 'description',
                            'total', 'Service Charge', 'GST', 'Final Amount']])
