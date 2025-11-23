## MONGODB

### users
```
user_id
name
method         # email_password, google
email
password
google_id
avatar_url
roles
create_at
update_at
```

### hierarchy
```
hierarchy_id
user_id
parent
children
create_at
update_at
```

### features
```
feature_id
name
description
create_at
update_at
```

### roles
```
role_id
name
permissions         # list feature_id if needed
create_at
update_at
```

### balances
```
balance_id
user_id
current_balance
create_at
update_at
```

### packages
```
package_id
name
price
duration_months
description
create_at
update_at
```

### subscriptions
```
subscription_id
user_id
package_id
start_day
end_day
status          # active, expired, canceled
is_auto_renew
create_at
update_at
```

### transactions
```
transaction_id
user_id
type            # purchase_package, usage, refund
amount
timestamp
description
```

### socials
```
social_id
name
logo_url
create_at
update_at
```

### social_accounts
```
social_account_id
social_id
user_id
social_account_user_id
social_account_name
social_account_avatar_url
social_account_access_token
create_at
update_at
```

### social_facebook_pages
```
fb_page_id
fb_page_name
fb_page_avatar
fb_page_access_token
social_account_id
is_connected        # bot có kết nối với page này không
webhook_verified    # webhook đã được verify chưa
create_at
update_at
```

### social_instagram_accounts
```
instagram_id
instagram_username
instagram_name
instagram_avatar
instagram_access_token
social_account_id
is_connected
create_at
update_at
```

### social_twitter_accounts
```
twitter_id
twitter_username
twitter_name
twitter_avatar
twitter_access_token
twitter_access_secret
social_account_id
is_connected
create_at
update_at
```

### social_linkedin_accounts
```
linkedin_id
linkedin_name
linkedin_avatar
linkedin_access_token
social_account_id
is_connected
create_at
update_at
```

### identities
```
identity_id
name
info
style
conversation_style
conversation_example
type            # default, custom
user_id
create_at
update_at
```

### procedures
```
procedure_id
name
procedure
type            # default, custom
user_id
create_at
update_at
```

### bots
```
bot_id
user_id
name
identity_id
procedure_id
role
target
mission
note
knowledge
type            # message, comment, post
status          # on, off
connect         # fb_page_id
create_at
update_at
```

## CRM

### companies 
```
company_id
name
website
industry
sub_industry
address
data [
    billing_address
    shipping_address
    phone
    email
    annual_revenue
    employee_count
    parent_company_id
    type                    # prospect, customer, partner, vendor, competitor
    status                  # active, inactive, archived
    priority                # high, medium, low
    customer_since
    partnership_level       # bronze, silver, gold, platinum
    credit_limit
    payment_terms           # net_30, net_60, cod
    tax_id
    custom_fields
    tags
]
user_id
create_at
update_at
```


### contacts
```
contact_id
user_id
type            # customer_info, business_human_resource,...
name
email
phone
address
company_id
data 
create_at
update_at
```

### products
```
product_id
name
sku             # mã sản phẩm
pricing
media           # [{"type": "images", "url": ""},...]
data
user_id
company_id
create_at
update_at
```

### warehouses
```
warehouse_id
name
address
inventory       # [{product_id, quantity, location_in_warehouse}]
user_id
company_id
create_at
update_at
```

### orders
```
order_id
code
contact_id
line_items      # list products
total_price
shipping_address
payment_method
status
user_id
company_id
create_at
update_at
```

### shipments
```
shipment_id
code
order_id
carrier
tracking_number
status
history
user_id
company_id
create_at
update_at
```

### knowledge_chunks
```
knowledge_id
content
content_embedding
source_info             # {"type": "", "source_id": "", "title": ""}
metadata                # {page_number, document_author, tags}
user_id
company_id
create_at
update_at
```

### documents
```
document_id
file_name
file_type
storage_type
storage_url
title
content
status
user_id
company_id
create_at
update_at
```

### histories
```
history_id
session_id
query
answer
media
status
user_id
company_id
bot_id
create_at
update_at
```

### feedback
```
feedback_id
user_id
social_id
social_identification       # {fb_page_id, sender_id, session_id}
content
status
create_at
update_at
```

### usage_tokens
```
usage_token_id
user_id
model
input_token
output_token
total_token
total_cost
message
timestamp
```

### automation_messenger
```
automation_id
type
social_id
social_identification
content
datetime
status
```

## SYSTEM MANAGEMENT

### notifications
```
notification_id
user_id
title
message
type            # info, warning, error, success
category        # system, bot, order, payment, social
is_read
data            # additional JSON data
create_at
update_at
```

### user_settings
```
setting_id
user_id
category        # notification, privacy, api, integration
setting_key
setting_value
create_at
update_at
```

### api_keys
```
api_key_id
user_id
key_name
api_key_hash
permissions     # list of allowed endpoints
is_active
last_used
usage_count
create_at
update_at
expires_at
```

### sessions
```
session_id
user_id
token_hash
device_info     # browser, os, ip
is_active
last_activity
create_at
expires_at
```

### audit_logs
```
log_id
user_id
action          # login, logout, create_bot, update_order, etc.
resource_type   # bot, order, contact, etc.
resource_id
old_data        # JSON before change
new_data        # JSON after change
ip_address
user_agent
timestamp
```


### support_tickets
```
ticket_id
user_id
subject
description
priority        # low, medium, high, urgent
status          # open, in_progress, resolved, closed
category        # technical, billing, feature_request
assigned_to     # support agent id
attachments     # file upload ids
create_at
update_at
```

### faqs
```
faq_id
question
answer
category
language
is_public
view_count
helpful_count
create_at
update_at
```

### feature_requests
```
request_id
user_id
title
description
category
priority
status          # submitted, under_review, planned, in_development, completed, rejected
votes_count
create_at
update_at
```

### webhooks
```
webhook_id
user_id
name
url
events          # list of events to listen
is_active
secret_key
retry_count
last_response
create_at
update_at
```

### templates
```
template_id
user_id
name
type            # message, email, notification
content
variables       # list of dynamic variables
language
is_default
create_at
update_at
```

### analytics_data
```
analytics_id
user_id
bot_id
date
metric_type     # messages_sent, conversations_started, orders_created
value
metadata        # additional context
create_at
```

### conversation_contexts
```
context_id
session_id
user_id
bot_id
current_step
context_data    # JSON state data
last_message_id
is_active
create_at
update_at
```

### languages
```
language_id
code            # vi, en, zh, etc.
name
is_active
create_at
update_at
```

### translations
```
translation_id
language_id
key_name
translated_text
category        # ui, bot, notification
create_at
update_at
```