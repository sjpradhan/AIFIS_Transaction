import requests
import io
import datetime
import numpy as np
import pandas as pd
import streamlit as st
import warnings

warnings.filterwarnings('ignore')


def main():
    profile_icon = "https://raw.githubusercontent.com/sjpradhan/aifis_transaction/master/transaction.png"

    st.set_page_config(page_title="Transaction-master",page_icon = profile_icon)

    st.header(":rainbow[Upload Transaction Master] 📁")

    # File uploader widget to upload Excel or Text file
    uploaded_file = st.file_uploader("Upload a Pipe-Delimited Text (.txt) or Excel (.xlsx/.xls) file",
                                     type=["xlsx", "xls", "txt"])

    # Check if a file is uploaded
    if uploaded_file is not None:

        # Handling Excel files
        if uploaded_file.type in ["application/vnd.ms-excel",
                                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
            st.write(":orange[The Dataset Has Been Uploaded as Excel File]")
            st.subheader("Original Data Preview:")
            # Read the Excel file into a pandas DataFrame
            df = pd.read_excel(uploaded_file)
            # st.write(df)  # Display the DataFrame

        # Handling Text files (pipe-delimited)
        elif uploaded_file.type == "text/plain":
            st.write(":orange[The Dataset Has Been Uploaded as Pipe-Delimited Text File]")
            # Read the text file content with pipe delimiter
            text_content = uploaded_file.getvalue().decode("utf-8")  # Decode bytes to string

            # Convert the text content into a pandas DataFrame
            from io import StringIO
            data = StringIO(text_content)  # Use StringIO to simulate a file object for pandas
            df = pd.read_csv(data, delimiter="|", header=None)  # Read the file with | as the delimiter
            headers = [
                "CLAIM_START_DATE",
                "CLAIM_END_DATE",
                "IFSC_CODE",
                "ACCOUNT_NUMBER",
                "TRANSACTION_DATE",
                "TRANSACTION_TYPE",
                "TRANSACTION_INDICATOR",
                "TRANSACTION_AMOUNT",
                "OUTSTANDING_AMT",
                "EFFECTIVE_PRINCP_DUE_AMT"
            ]
            df.columns = headers
            df['TRANSACTION_DATE'] = pd.to_datetime(df['TRANSACTION_DATE'], format='%d-%m-%Y')
            df['CLAIM_START_DATE'] = pd.to_datetime(df['CLAIM_START_DATE'], format='%d-%m-%Y')
            df['CLAIM_END_DATE'] = pd.to_datetime(df['CLAIM_END_DATE'], format='%d-%m-%Y')
            df['ACCOUNT_NUMBER'] = df['ACCOUNT_NUMBER'].astype(str)

        original_df_shape = df.shape
        unique_account_number = df['ACCOUNT_NUMBER'].nunique()
        st.write("Total Unique Accout Number", unique_account_number)
        st.write("Number Of Records In Original File", original_df_shape)
        st.write(df)

        # Initialize a running balance column
        transaction = df
        transaction['RUNNING_BALANCE'] = 0

        # Define the initial balance
        initial_balance = 0

        # Define a function to update the running balance
        def update_running_balance(row, previous_balance):
            if row['TRANSACTION_INDICATOR'] == 'O':
                balance = row['TRANSACTION_AMOUNT']
            elif row['TRANSACTION_INDICATOR'] == 'P':
                balance = previous_balance
            elif row['TRANSACTION_INDICATOR'] == 'D':
                balance = previous_balance + row['TRANSACTION_AMOUNT']
            elif row['TRANSACTION_INDICATOR'] == 'C':
                balance = previous_balance - row['TRANSACTION_AMOUNT']
            elif row['TRANSACTION_INDICATOR'] == 'B':
                balance = previous_balance + row['TRANSACTION_AMOUNT']
            elif row['TRANSACTION_INDICATOR'] == 'L':
                balance = previous_balance
            return balance

        # Iterate through the DataFrame and update the running balance
        for i in range(len(transaction)):
            if i == 0:
                transaction.at[i, 'RUNNING_BALANCE'] = update_running_balance(transaction.iloc[i], initial_balance)
            else:
                transaction.at[i, 'RUNNING_BALANCE'] = update_running_balance(transaction.iloc[i],
                                                                              transaction.at[i - 1, 'RUNNING_BALANCE'])

        # Initialize a principle balance column
        transaction['PRINCIPLE_BALANCE'] = 0

        # Define the initial balance
        initial_balance = 0

        # Define a function to update the principle balance
        def update_principle_balance(row, previous_balance):
            if row['TRANSACTION_INDICATOR'] == 'O':
                balance = row['EFFECTIVE_PRINCP_DUE_AMT']
            elif row['TRANSACTION_INDICATOR'] == 'P':
                balance = previous_balance - row['TRANSACTION_AMOUNT']
            elif row['TRANSACTION_INDICATOR'] == 'D':
                balance = previous_balance
            elif row['TRANSACTION_INDICATOR'] == 'C':
                balance = previous_balance
            elif row['TRANSACTION_INDICATOR'] == 'B':
                balance = previous_balance + row['TRANSACTION_AMOUNT']
            elif row['TRANSACTION_INDICATOR'] == 'L':
                balance = previous_balance
            return balance

        # Iterate through the DataFrame and update the running balance
        for i in range(len(transaction)):
            if i == 0:
                transaction.at[i, 'PRINCIPLE_BALANCE'] = update_principle_balance(transaction.iloc[i], initial_balance)
            else:
                transaction.at[i, 'PRINCIPLE_BALANCE'] = update_principle_balance(transaction.iloc[i], transaction.at[
                    i - 1, 'PRINCIPLE_BALANCE'])

        transaction['RUNNING_BALANCE_CHECK'] = transaction['OUTSTANDING_AMT'] - transaction['RUNNING_BALANCE']
        transaction['PRINCIPLE_BALANCE_CHECK'] = transaction['EFFECTIVE_PRINCP_DUE_AMT'] - transaction[
            'PRINCIPLE_BALANCE']

        tolerance = 1e-8
        transaction.loc[
            np.isclose(transaction['RUNNING_BALANCE_CHECK'], 0, atol=tolerance), 'RUNNING_BALANCE_CHECK'] = 0

        tolerance = 1e-8
        transaction.loc[
            np.isclose(transaction['PRINCIPLE_BALANCE_CHECK'], 0, atol=tolerance), 'PRINCIPLE_BALANCE_CHECK'] = 0

        # Filter rows where the RUNNING_BALANCE_CHECK is not zero
        compare_running_balance = transaction[transaction['RUNNING_BALANCE_CHECK'] != 0]

        # Filter rows where the PRINCIPLE_BALANCE_CHECK is not zero
        compare_principle_balance = transaction[transaction['PRINCIPLE_BALANCE_CHECK'] != 0]

        col1, col2 = st.columns(2)
        has_error = False

        with col1:
            st.write("Outstanding Balance")
            if not compare_running_balance.empty:
                st.error(
                    f"Error occurred in outstanding balance amount at line number: {', '.join(map(str, compare_running_balance.index.tolist()))}")
                st.success("Outstanding balalnce has been updated to its actual value.")
                has_error = True
            else:
                st.success("No error in Outstanding Balance.")

        with col2:
            st.write("Principal Balance")
            if not compare_principle_balance.empty:
                st.error(
                    f"Error occurred in principal balance amount at line number: {', '.join(map(str, compare_principle_balance.index.tolist()))}")
                st.success("Principal balalnce has been updated to its actual value.")
                has_error = True
            else:
                st.success("No error in Principal Balance.")

        if has_error:
            transaction['OUTSTANDING_AMT'].update(transaction['RUNNING_BALANCE'])
            transaction['EFFECTIVE_PRINCP_DUE_AMT'].update(transaction['PRINCIPLE_BALANCE'])

            transaction = transaction.iloc[0:, 0: 10]
            st.subheader("Updated Data Preview")
            st.write(transaction)
        else:
            st.write("")
        df = transaction

        # Create a new dataframe to store the expanded data
        expanded_data = []

        # Group by Account Number and find the date range for each account
        for account, group in df.groupby('ACCOUNT_NUMBER'):
            min_date = group['CLAIM_START_DATE'].min()
            max_date = group['CLAIM_END_DATE'].max()

            # Generate all dates between min_date and max_date
            date_range = pd.date_range(min_date, max_date)

            # For each date in the range, check if a transaction exists
            for date in date_range:
                # Check for transactions on this date
                transactions_on_date = group[group['TRANSACTION_DATE'] == date]

                # If there are transactions, add them to the expanded data
                if not transactions_on_date.empty:
                    for _, row in transactions_on_date.iterrows():
                        expanded_data.append({
                            'CLAIM_START_DATE': row['CLAIM_START_DATE'],
                            'CLAIM_END_DATE': row['CLAIM_END_DATE'],
                            'IFSC_CODE': row['IFSC_CODE'],
                            'ACCOUNT_NUMBER': row['ACCOUNT_NUMBER'],
                            'TRANSACTION_TYPE': row['TRANSACTION_TYPE'],
                            'TRANSACTION_INDICATOR': row['TRANSACTION_INDICATOR'],
                            'TRANSACTION_DATE': date,
                            'TRANSACTION_AMOUNT': row['TRANSACTION_AMOUNT'],
                            'OUTSTANDING_AMT': row['OUTSTANDING_AMT'],
                            'EFFECTIVE_PRINCP_DUE_AMT': row['EFFECTIVE_PRINCP_DUE_AMT']
                        })
                else:
                    # If there are no transactions, add a blank row with NaN for transaction amount and other columns
                    expanded_data.append({
                        'CLAIM_START_DATE': min_date,
                        'CLAIM_END_DATE': max_date,
                        'IFSC_CODE': group['IFSC_CODE'].iloc[0],
                        'ACCOUNT_NUMBER': account,
                        'TRANSACTION_TYPE': pd.NA,
                        'TRANSACTION_INDICATOR': pd.NA,
                        'TRANSACTION_DATE': date,
                        'TRANSACTION_AMOUNT': pd.NA,
                        'OUTSTANDING_AMT': pd.NA,
                        'EFFECTIVE_PRINCP_DUE_AMT': pd.NA
                    })
        expanded_df = pd.DataFrame(expanded_data)

        expanded_df[['TRANSACTION_TYPE', 'TRANSACTION_INDICATOR', 'TRANSACTION_AMOUNT', 'OUTSTANDING_AMT',
                     'EFFECTIVE_PRINCP_DUE_AMT']] = expanded_df.groupby('ACCOUNT_NUMBER')[
            ['TRANSACTION_TYPE', 'TRANSACTION_INDICATOR', 'TRANSACTION_AMOUNT', 'OUTSTANDING_AMT',
             'EFFECTIVE_PRINCP_DUE_AMT']].fillna(method='ffill')
        expanded_df_shape = expanded_df.shape

        # expanded_df['Interest subvention'] = (
        #     expanded_df[['OUTSTANDING_AMT', 'EFFECTIVE_PRINCP_DUE_AMT']].min(axis=1) * 0.03 / 366         # Calculate Interest Subvention
        # ).round(2)

        st.write("Number Of Rows After Expanded", expanded_df_shape)

        # Function to convert DataFrame to a pipe-delimited .txt string
        def convert_df_to_txt(expanded_df):
            return expanded_df.to_csv(index=False, sep='|')  # Pipe-delimited format

        # Function to convert DataFrame to an Excel file
        def convert_df_to_excel(expanded_df):
            output = io.BytesIO()  # Create a BytesIO object to store the file in memory
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                expanded_df.to_excel(writer, index=False, sheet_name='Sheet1')
            output.seek(0)  # Seek to the start of the file
            return output

        col1, col2 = st.columns(2)

        with col1:
            # Create a dropdown menu to select file type
            file_type = st.selectbox(
                "Select the file format to download:",
                ["Text (.txt)", "Excel (.xlsx)"]
            )

            # Create the download buttons based on the file type selected
            if file_type == "Text (.txt)":
                # Create the button to download as .txt
                txt = convert_df_to_txt(expanded_df)
                st.download_button(
                    label="Download as Text (.txt)",
                    data=txt,
                    file_name=f"transaction_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    # Set the default filename
                    mime="text/plain"  # MIME type for text files
                )

            elif file_type == "Excel (.xlsx)":
                # Create the button to download as .xlsx
                excel = convert_df_to_excel(expanded_df)
                st.download_button(
                    label="Download as Excel (.xlsx)",
                    data=excel,
                    file_name=f"transaction_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    # Set the default filename
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    # MIME type for Excel files
                )

if __name__ == "__main__":
    main()