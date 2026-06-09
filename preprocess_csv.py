import pandas as pd

# Disposition data is a list of dispositions
disposition_data = []
df = pd.read_csv("csv/dispositions.csv")
for row in df.itertuples(index=False, name=None):
    data = {
        "Category": row[0],
        "Priority": row[1],
        "Disposition Code": row[2],
        "Description": row[3]
    }
    disposition_data.append(data)

# Disposition data formatted is a formatted string of the disposition data
disposition_data_formated = "\n".join([
    f"{i+1}. CATEGORY: {x['Category']} | PRIORITY: {x['Priority']} | CODE: {x['Disposition Code']} | DESCRIPTION: {x['Description']}"
    for i, x in enumerate(disposition_data)
])


# Grievance data is a list of grievances
disposition_data_grievance = []
df_grievance_csv = pd.read_csv("csv/Grievance_Categories.csv")
for row in df_grievance_csv.itertuples(index=False, name=None):
    data = {
        "parent_disposition_code": row[0],
        "sub_category_code": row[1],
        "sub_category_label": row[2],
        "description_hindi": row[3]
    }
    disposition_data_grievance.append(data)

# Grievance data formatted is a formatted string of the grievance data
disposition_data_grievance_formated = "\n".join([
    f"{i+1}. CODE: {x['sub_category_code']} | LABEL: {x['sub_category_label']} | DESC: {x['description_hindi']}"
    for i, x in enumerate(disposition_data_grievance)
])

# Get disposition data is a function that returns the disposition data
def get_disposition_data():
    return disposition_data_formated, disposition_data

# Get grievance data is a function that returns the grievance data
def get_disposition_data_grievance():
    return disposition_data_grievance_formated, disposition_data_grievance