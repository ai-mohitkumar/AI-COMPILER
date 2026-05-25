from __future__ import annotations

DOMAIN_ALIASES: dict[str, list[str]] = {
    "crm": ["crm", "customer", "lead", "leads", "sales pipeline", "contact management", "follow up", "follow-up"],
    "hrms": ["hr", "hrms", "employee", "leave", "payroll", "recruitment"],
    "lms": ["lms", "learning", "course", "student", "training", "academy"],
    "inventory": ["inventory", "warehouse", "stock", "sku", "procurement"],
    "ecommerce": ["ecommerce", "e-commerce", "shop", "store", "order", "cart"],
    "project_management": ["project", "task", "sprint", "team", "milestone"],
    "generic_workspace": ["workspace", "portal", "operations", "management"],
}


FEATURE_KEYWORDS: dict[str, list[str]] = {
    "auth": ["login", "sign in", "authentication", "auth", "permission", "role"],
    "analytics": ["analytics", "report", "dashboard", "kpi", "insight"],
    "approvals": ["approval", "approve", "workflow", "escalation"],
    "notifications": ["notification", "alert", "reminder", "email"],
    "search": ["search", "filter", "find"],
    "comments": ["comment", "discussion", "note"],
    "tasks": ["task", "todo", "activity", "follow up"],
    "inventory_tracking": ["inventory", "stock", "warehouse"],
    "commerce": ["order", "payment", "checkout", "cart"],
}


ROLE_KEYWORDS: dict[str, list[str]] = {
    "admin": ["admin", "administrator"],
    "manager": ["manager", "lead", "supervisor"],
    "sales_rep": ["sales rep", "salesperson", "sales"],
    "employee": ["employee", "staff"],
    "student": ["student", "learner"],
    "instructor": ["teacher", "trainer", "instructor"],
    "warehouse_manager": ["warehouse manager", "inventory manager"],
    "customer": ["customer", "buyer"],
    "member": ["member", "user"],
}


DOMAIN_TEMPLATES: dict[str, dict] = {
    "crm": {
        "app_type": "CRM",
        "summary": "Manage customer relationships, pipeline activity, and reporting.",
        "features": ["auth", "contacts", "tasks", "analytics", "search"],
        "roles": ["admin", "manager", "sales_rep"],
        "entities": [
            {
                "name": "contacts",
                "description": "Leads and customers managed by the sales team.",
                "primary_display_field": "full_name",
                "fields": [
                    {"name": "full_name", "type": "string", "searchable": True},
                    {"name": "email", "type": "string", "searchable": True},
                    {"name": "company", "type": "string", "filterable": True},
                    {"name": "status", "type": "string", "filterable": True},
                ],
            },
            {
                "name": "activities",
                "description": "Sales calls, meetings, and follow-up tasks.",
                "primary_display_field": "title",
                "fields": [
                    {"name": "title", "type": "string", "searchable": True},
                    {"name": "activity_type", "type": "string", "filterable": True},
                    {"name": "due_date", "type": "date"},
                    {"name": "contact_id", "type": "uuid", "reference_entity": "contacts"},
                ],
            },
        ],
    },
    "hrms": {
        "app_type": "HRMS",
        "summary": "Track employees, leave requests, and approvals.",
        "features": ["auth", "approvals", "analytics", "search"],
        "roles": ["admin", "manager", "employee"],
        "entities": [
            {
                "name": "employees",
                "description": "Core employee profiles and employment details.",
                "primary_display_field": "full_name",
                "fields": [
                    {"name": "full_name", "type": "string", "searchable": True},
                    {"name": "department", "type": "string", "filterable": True},
                    {"name": "job_title", "type": "string"},
                    {"name": "employment_status", "type": "string", "filterable": True},
                ],
            },
            {
                "name": "leave_requests",
                "description": "Time-off requests that move through approval workflows.",
                "primary_display_field": "request_type",
                "fields": [
                    {"name": "employee_id", "type": "uuid", "reference_entity": "employees"},
                    {"name": "request_type", "type": "string", "filterable": True},
                    {"name": "start_date", "type": "date"},
                    {"name": "status", "type": "string", "filterable": True},
                ],
            },
        ],
    },
    "lms": {
        "app_type": "LMS",
        "summary": "Deliver courses, manage learners, and track progress.",
        "features": ["auth", "analytics", "search"],
        "roles": ["admin", "instructor", "student"],
        "entities": [
            {
                "name": "courses",
                "description": "Courses available to learners.",
                "primary_display_field": "title",
                "fields": [
                    {"name": "title", "type": "string", "searchable": True},
                    {"name": "category", "type": "string", "filterable": True},
                    {"name": "duration_hours", "type": "integer"},
                    {"name": "status", "type": "string", "filterable": True},
                ],
            },
            {
                "name": "learners",
                "description": "Users enrolled in learning programs.",
                "primary_display_field": "full_name",
                "fields": [
                    {"name": "full_name", "type": "string", "searchable": True},
                    {"name": "email", "type": "string", "searchable": True},
                    {"name": "cohort", "type": "string", "filterable": True},
                ],
            },
            {
                "name": "enrollments",
                "description": "Enrollment records for learners and courses.",
                "primary_display_field": "status",
                "fields": [
                    {"name": "course_id", "type": "uuid", "reference_entity": "courses"},
                    {"name": "learner_id", "type": "uuid", "reference_entity": "learners"},
                    {"name": "status", "type": "string", "filterable": True},
                    {"name": "progress_percent", "type": "integer"},
                ],
            },
        ],
    },
    "inventory": {
        "app_type": "Inventory System",
        "summary": "Track products, suppliers, and stock movement.",
        "features": ["auth", "inventory_tracking", "analytics", "search"],
        "roles": ["admin", "warehouse_manager", "member"],
        "entities": [
            {
                "name": "products",
                "description": "Products and SKUs held in stock.",
                "primary_display_field": "name",
                "fields": [
                    {"name": "name", "type": "string", "searchable": True},
                    {"name": "sku", "type": "string", "searchable": True},
                    {"name": "category", "type": "string", "filterable": True},
                    {"name": "quantity_on_hand", "type": "integer"},
                ],
            },
            {
                "name": "suppliers",
                "description": "Suppliers providing stocked products.",
                "primary_display_field": "name",
                "fields": [
                    {"name": "name", "type": "string", "searchable": True},
                    {"name": "contact_email", "type": "string"},
                    {"name": "rating", "type": "float"},
                ],
            },
            {
                "name": "stock_movements",
                "description": "Inbound and outbound inventory transactions.",
                "primary_display_field": "movement_type",
                "fields": [
                    {"name": "product_id", "type": "uuid", "reference_entity": "products"},
                    {"name": "supplier_id", "type": "uuid", "reference_entity": "suppliers", "required": False},
                    {"name": "movement_type", "type": "string", "filterable": True},
                    {"name": "quantity", "type": "integer"},
                ],
            },
        ],
    },
    "ecommerce": {
        "app_type": "Ecommerce",
        "summary": "Manage products, customers, and orders.",
        "features": ["auth", "commerce", "analytics", "search"],
        "roles": ["admin", "manager", "customer"],
        "entities": [
            {
                "name": "products",
                "description": "Products available for purchase.",
                "primary_display_field": "name",
                "fields": [
                    {"name": "name", "type": "string", "searchable": True},
                    {"name": "price", "type": "float"},
                    {"name": "category", "type": "string", "filterable": True},
                    {"name": "inventory_count", "type": "integer"},
                ],
            },
            {
                "name": "customers",
                "description": "Customers placing orders.",
                "primary_display_field": "full_name",
                "fields": [
                    {"name": "full_name", "type": "string", "searchable": True},
                    {"name": "email", "type": "string", "searchable": True},
                    {"name": "status", "type": "string", "filterable": True},
                ],
            },
            {
                "name": "orders",
                "description": "Placed orders and fulfillment state.",
                "primary_display_field": "order_number",
                "fields": [
                    {"name": "order_number", "type": "string", "searchable": True},
                    {"name": "customer_id", "type": "uuid", "reference_entity": "customers"},
                    {"name": "status", "type": "string", "filterable": True},
                    {"name": "total_amount", "type": "float"},
                ],
            },
        ],
    },
    "project_management": {
        "app_type": "Project Management",
        "summary": "Track projects, tasks, and delivery progress.",
        "features": ["auth", "tasks", "analytics", "search", "comments"],
        "roles": ["admin", "manager", "member"],
        "entities": [
            {
                "name": "projects",
                "description": "Projects managed by the team.",
                "primary_display_field": "name",
                "fields": [
                    {"name": "name", "type": "string", "searchable": True},
                    {"name": "owner", "type": "string"},
                    {"name": "status", "type": "string", "filterable": True},
                    {"name": "priority", "type": "string", "filterable": True},
                ],
            },
            {
                "name": "tasks",
                "description": "Tasks and deliverables within projects.",
                "primary_display_field": "title",
                "fields": [
                    {"name": "project_id", "type": "uuid", "reference_entity": "projects"},
                    {"name": "title", "type": "string", "searchable": True},
                    {"name": "assignee", "type": "string"},
                    {"name": "status", "type": "string", "filterable": True},
                ],
            },
        ],
    },
    "generic_workspace": {
        "app_type": "Operations Workspace",
        "summary": "Manage records, team workflows, and operational visibility.",
        "features": ["auth", "search", "analytics"],
        "roles": ["admin", "manager", "member"],
        "entities": [
            {
                "name": "records",
                "description": "Primary records managed by the workspace.",
                "primary_display_field": "name",
                "fields": [
                    {"name": "name", "type": "string", "searchable": True},
                    {"name": "status", "type": "string", "filterable": True},
                    {"name": "owner", "type": "string"},
                ],
            },
            {
                "name": "work_items",
                "description": "Tasks or follow-ups attached to records.",
                "primary_display_field": "title",
                "fields": [
                    {"name": "record_id", "type": "uuid", "reference_entity": "records"},
                    {"name": "title", "type": "string", "searchable": True},
                    {"name": "status", "type": "string", "filterable": True},
                ],
            },
        ],
    },
}
