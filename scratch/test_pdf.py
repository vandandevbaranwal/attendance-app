from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def test_pdf():
    pdf_filename = "scratch/test_report.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        spaceAfter=12,
        textColor=colors.HexColor("#1e293b")
    )
    
    story.append(Paragraph("Attendance Report", title_style))
    story.append(Spacer(1, 12))
    
    data = [
        ["S.No.", "Roll No (Last 2)", "Name"],
        [1, "01", "Aaryan Krish"],
        [2, "02", "Abhiraj Chaurasia"]
    ]
    
    t = Table(data, colWidths=[50, 100, 250])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2563eb")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
    ]))
    
    story.append(t)
    doc.build(story)
    print("PDF generated successfully.")

if __name__ == "__main__":
    test_pdf()
