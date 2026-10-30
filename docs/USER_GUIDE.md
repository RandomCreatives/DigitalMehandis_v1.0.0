# EthioQS User Guide

## Getting Started

### 1. Create an Account
Go to the app URL → click **Get Started Free** → fill in your details → **Create Account**.

### 2. Create a Project
From the dashboard → **New Project** → enter:
- Project name
- Location (Ethiopian city)
- Code of practice (default: EBCS)
- Click **Create Project**

---

## Uploading Drawings

1. Open your project → click **Drawings**
2. Select the drawing category (Architectural / Structural / Electrical / Sanitary)
3. Drag & drop your PDF files or click to browse
4. Files appear in the list once uploaded
5. Click the eye icon to view a drawing in the browser

**Supported formats:** PDF only (Phase 1)
**Max file size:** 100 MB per file

---

## Take-off Sheet

1. Open your project → click **Take-off**
2. Switch between **Substructure** and **Superstructure** tabs
3. For each item:
   - Enter description (e.g. "C-25 Concrete")
   - Select unit (m³, m², m, Nr, kg, etc.)
   - Enter quantity
   - Click **Add**
4. Edit quantities inline by clicking the quantity field
5. Delete items with the trash icon

---

## Generating BOQ

1. Open your project → click **BOQ**
2. Select section: Combined / Substructure / Superstructure
3. Click **Generate BOQ**
4. The system matches your take-off items to the pre-loaded Ethiopian rate database
5. Export to **Excel** or **PDF** using the buttons

**Note:** Items without a matching rate are skipped. Add custom rates via the API if needed.

---

## Bar Bending Schedule (BBS)

1. Open your project → click **BBS**
2. Select section (Substructure / Superstructure)
3. For each bar, fill in:
   - Member name (e.g. "Footing F1")
   - Bar diameter (6–32mm)
   - Bar shape (Straight, L-Shape, Hook, U-Shape, Spiral)
   - Quantity, clear length, cover, hook length
   - Code of practice for laps: **ES EN 1992-1-1:2015** (formula, default) or **EBCS-2:1995** (site practice)
4. The **live preview** shows cutting length, weight, and lap length before saving
5. Click **Add Bar** to save
6. View the **Cutting List** for supplier batch-cutting orders
7. Export to **Excel** (includes BBS sheet + Cutting List sheet)

### BBS Calculation Reference

| Shape | Formula |
|-------|---------|
| Straight | Clear length + 2 × cover |
| L-Shape | 2 × clear length − 2d + 2 × cover |
| Hook | Clear length + hook length + 2 × cover |
| U-Shape | 2 × clear length + hook length − 2d + 2 × cover |
| Spiral | 2 × clear length − 4d |

Lap length depends on the code of practice you select:

| Code | Method | Value for φ16, C25/30 |
|------|--------|-----------------------|
| **ES EN 1992-1-1:2015 §8.4.4** (default) | `l_0 = α₁α₂α₃α₅α₆·l_b,rqd`, computed from f_bd | **969 mm** |
| **EBCS-2:1995** (site practice) | 50φ approximation | 800 mm |

> **Citations that are correct for a BBS:** ES EN 1992-1-1:2015 §8 for anchorage and
> laps, BS 8666 for shape codes and bend deductions. *EBCS-3 is Design of Steel
> Structures* — it does not govern reinforced-concrete bar schedules. ES EN
> 1992-1-1:2015 superseded and withdrew EBCS-2:1995, but Ethiopian site practice
> still says "EBCS", so both are supported. Every bar records which code produced
> its lap length, so the schedule can be audited.

### Concrete grade conventions

Ethiopian BoQs say "C-25"; drawings say "C25/30". **They are not the same mix:**

| Convention | Code | Meaning of "C-25" | Cylinder f_ck | Rate key |
|------------|------|-------------------|---------------|----------|
| Cube | EBCS-2:1995 | f_cu = 25 MPa | 20.0 MPa | `C20/25` |
| Cylinder | ES EN 1992-1-1:2015 | f_ck,cyl = 25 MPa | 25.0 MPa | `C25/30` |

`f_ck,cyl ≈ 0.80 × f_cu`. The app records which convention each element was priced
in and keys rates on the convention-aware key, so a cube price can never be matched
to a cylinder-specified item. On a φ16 bar this changes the scheduled lap by
**155 mm** — and on a concrete price it changes the mix you are buying.

---

## Exporting

| Format | BOQ | BBS |
|--------|-----|-----|
| Excel (.xlsx) | ✅ | ✅ (BBS + Cutting List sheets) |
| PDF | ✅ | Coming in Phase 2 |

---

## Rate Database

EthioQS comes pre-loaded with Ethiopian construction rates including:
- Excavation & earthworks
- C-25, C-30, C-20 concrete
- Reinforcement steel (all diameters)
- Hollow block walls
- Formwork
- Plastering, painting, tiling
- Roofing (EGA sheets, timber trusses)
- Doors & windows

Rates are based on MoWUD direct-cost publications and Addis Ababa market surveys (2024).
