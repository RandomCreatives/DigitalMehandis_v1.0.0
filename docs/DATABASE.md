# Database Schema

## Tables

### users
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| email | VARCHAR(255) UNIQUE | login identifier |
| password_hash | VARCHAR(255) | bcrypt |
| full_name | VARCHAR(255) | optional |
| organization | VARCHAR(255) | optional |
| role | VARCHAR(50) | STUDENT / QS_PROFESSIONAL / CONTRACTOR / ADMIN |
| preferred_language | VARCHAR(5) | EN / AM |
| email_verified | BOOLEAN | default false |
| created_at / updated_at | TIMESTAMP | UTC |

### projects
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID FK → users | cascade delete |
| name | VARCHAR(255) | required |
| location | VARCHAR(255) | Ethiopian city |
| code_of_practice | VARCHAR(50) | EBCS / BS / IS_CODE / EUROCODE |
| unit_system | VARCHAR(10) | METRIC / IMPERIAL |
| currency | VARCHAR(3) | default ETB |
| scale | VARCHAR(50) | e.g. 1:100 |

### drawings
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| project_id | UUID FK → projects | cascade delete |
| filename | VARCHAR(255) | original name |
| file_path | VARCHAR(500) | server filesystem path |
| category | VARCHAR(50) | ARCHITECTURAL / STRUCTURAL / ELECTRICAL / SANITARY |
| page_count | INT | extracted from PDF |
| scale | VARCHAR(50) | user-set or OCR-extracted |

### takeoff_items
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| project_id | UUID FK → projects | |
| description | VARCHAR(500) | item description |
| unit | VARCHAR(50) | m³, m², m, Nr, kg, etc. |
| quantity | NUMERIC(15,3) | |
| section | VARCHAR(50) | SUBSTRUCTURE / SUPERSTRUCTURE |

### rates
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| project_id | UUID FK nullable | NULL = global rate |
| item_code | VARCHAR(50) | e.g. CONC001 |
| description | VARCHAR(500) | |
| unit | VARCHAR(50) | |
| rate_per_unit | NUMERIC(15,2) | ETB |
| rate_source | VARCHAR(255) | MoWUD 2018 Q3 / Market Survey |
| region | VARCHAR(255) | Addis Ababa / National Average |

### bbs_bars
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| project_id | UUID FK → projects | |
| bar_mark | VARCHAR(50) | auto B1, B2, … |
| member_name | VARCHAR(255) | Footing F1, Column C1, etc. |
| bar_diameter_mm | INT | 6/8/10/12/16/20/25/32 |
| bar_shape | VARCHAR(50) | STRAIGHT/L_SHAPE/HOOK/U_SHAPE/SPIRAL |
| quantity | INT | number of bars |
| clear_length_m | NUMERIC(8,3) | |
| hook_length_mm | INT | default 0 |
| cover_top_mm / cover_bottom_mm | INT | default 50 |
| lap_length_mm | INT | calculated per `design_code` (ES EN 1992-1-1 §8.4.4 formula, or EBCS-2 50φ practice) |
| design_code | VARCHAR(40) | which code produced lap_length_mm |
| concrete_grade | VARCHAR(20) | grade used for the lap calc, e.g. C25/30 |
| section | VARCHAR(50) | SUBSTRUCTURE / SUPERSTRUCTURE |

### boq_outputs
Cached BOQ generation results with PDF/Excel file paths.

## Relationships
```
users ──< projects ──< drawings
                  ──< takeoff_items
                  ──< rates (project-specific overrides)
                  ──< bbs_bars
                  ──< boq_outputs
```
