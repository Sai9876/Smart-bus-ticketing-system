from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A5

def save_ticket_pdf(ticket: dict, passengers: list, out_path: str):
    c = canvas.Canvas(out_path, pagesize=A5)
    y = 520

    # --- Ticket Header ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Smart Bus Ticket")
    y -= 30

    # --- PNR prominently ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, f"PNR: {ticket.get('pnr', '-')}")
    y -= 25

    # --- Ticket details ---
    c.setFont("Helvetica", 11)
    for k in ["id", "boarding", "dropping", "time_slot", "seats", "seat_labels", "final_fare", "phone"]:
        c.drawString(40, y, f"{k}: {ticket.get(k, '')}")
        y -= 22

    # --- Passengers section ---
    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Passengers:")
    y -= 22

    c.setFont("Helvetica", 11)
    for p in passengers:
        c.drawString(60, y, f"- {p['name']} ({p['age']})")
        y -= 20

    # --- Finalize PDF ---
    c.showPage()
    c.save()
    return out_path
