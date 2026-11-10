"""
PDF Report Generator for FedEx Non-Delivered Tracking IDs
Handles PDF generation with customization options
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, legal
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
from typing import Optional, List, Dict, Any
import re
from io import BytesIO


class PDFReportConfig:
    """Configuration for PDF report customization"""
    
    def __init__(
        self,
        page_size: str = "letter",  # letter, A4, legal
        orientation: str = "portrait",  # portrait, landscape
        title: str = "FedEx Non-Delivered Tracking Report",
        company_name: str = "FedEx Corporation",
        logo_path: Optional[str] = None,
        header_color: str = "#4B0082",  # FedEx purple
        table_header_color: str = "#E6E6FA",  # Light purple
        show_footer: bool = True,
        show_page_numbers: bool = True,
        font_name: str = "Helvetica",
        font_size: int = 10,
        include_summary: bool = True,
        columns: Optional[List[str]] = None,
        max_records: Optional[int] = None
    ):
        self.page_size = self._get_page_size(page_size, orientation)
        self.title = title
        self.company_name = company_name
        self.logo_path = logo_path
        self.header_color = header_color
        self.table_header_color = table_header_color
        self.show_footer = show_footer
        self.show_page_numbers = show_page_numbers
        self.font_name = font_name
        self.font_size = font_size
        self.include_summary = include_summary
        self.max_records = max_records
        self.columns = columns
    
    def _get_page_size(self, size: str, orientation: str):
        """Get page size based on configuration"""
        sizes = {
            "letter": letter,
            "a4": A4,
            "legal": legal
        }
        page = sizes.get(size.lower(), letter)
        
        if orientation.lower() == "landscape":
            return (page[1], page[0])
        return page


class FedExPDFGenerator:
    """Generate customized PDF reports for FedEx tracking data"""
    
    def __init__(self, config: Optional[PDFReportConfig] = None):
        self.config = config or PDFReportConfig()
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor(self.config.header_color),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName=f'{self.config.font_name}-Bold'
        ))
        
        # Header style
        self.styles.add(ParagraphStyle(
            name='CustomHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor(self.config.header_color),
            spaceAfter=12,
            fontName=f'{self.config.font_name}-Bold'
        ))
        
        # Subheader style
        self.styles.add(ParagraphStyle(
            name='CustomSubHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceAfter=10,
            fontName=f'{self.config.font_name}-Bold'
        ))

        # Table header cell style — white bold text for use inside Paragraph objects in table header rows
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            parent=self.styles['Normal'],
            fontSize=7,
            textColor=colors.whitesmoke,
            fontName=f'{self.config.font_name}-Bold',
            leading=9,
            wordWrap='LTR'
        ))

        # Table data cell style
        self.styles.add(ParagraphStyle(
            name='TableCell',
            parent=self.styles['Normal'],
            fontSize=6.5,
            textColor=colors.black,
            fontName=self.config.font_name,
            leading=8,
            wordWrap='LTR'
        ))
    
    def generate_report(
        self,
        data: Dict[str, Any],
        output_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Generate PDF report from tracking data
        
        Args:
            data: Dictionary containing tracking data
            output_path: Optional file path to save PDF (if None, returns bytes)
            metadata: Optional metadata (facilityId, scanDate, etc.)
        
        Returns:
            PDF as bytes
        """
        # Create PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer if not output_path else output_path,
            pagesize=self.config.page_size,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=1*inch,
            bottomMargin=0.75*inch
        )
        
        # Build PDF content
        story = []
        
        # Add logo if provided
        if self.config.logo_path:
            try:
                logo = Image(self.config.logo_path, width=2*inch, height=0.5*inch)
                logo.hAlign = 'LEFT'
                story.append(logo)
                story.append(Spacer(1, 0.2*inch))
            except:
                pass  # Skip logo if file not found
        
        # Add title
        title = Paragraph(self.config.title, self.styles['CustomTitle'])
        story.append(title)
        story.append(Spacer(1, 0.3*inch))
        
        # Add company name
        company = Paragraph(
            f"<b>{self.config.company_name}</b>",
            self.styles['Normal']
        )
        story.append(company)
        story.append(Spacer(1, 0.2*inch))
        
        # Add generation date
        gen_date = Paragraph(
            f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            self.styles['Normal']
        )
        story.append(gen_date)
        story.append(Spacer(1, 0.3*inch))
        
        # Add metadata section if provided
        if metadata:
            story.append(Paragraph("Report Parameters", self.styles['CustomHeader']))
            metadata_table = self._create_metadata_table(metadata)
            story.append(metadata_table)
            story.append(Spacer(1, 0.3*inch))
        
        # Add summary section if enabled
        if self.config.include_summary:
            summary = self._create_summary_section(data)
            story.extend(summary)
            story.append(Spacer(1, 0.3*inch))
        
        # Add tracking data table
        story.append(Paragraph("Non-Delivered Tracking IDs", self.styles['CustomHeader']))
        tracking_table = self._create_tracking_table(data)
        story.append(tracking_table)
        
        # Add footer
        if self.config.show_footer:
            story.append(Spacer(1, 0.5*inch))
            footer = Paragraph(
                f"<i>Confidential - For Internal Use Only</i>",
                self.styles['Normal']
            )
            story.append(footer)
        
        # Build PDF
        doc.build(story)
        
        # Return bytes if no output path
        if not output_path:
            buffer.seek(0)
            return buffer.read()
        
        return None
    
    def _create_metadata_table(self, metadata: Dict[str, Any]) -> Table:
        """Create metadata information table"""
        data = []
        for key, value in metadata.items():
            data.append([
                Paragraph(f"<b>{key.replace('_', ' ').title()}:</b>", self.styles['Normal']),
                Paragraph(str(value), self.styles['Normal'])
            ])
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor(self.config.table_header_color)),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), self.config.font_name),
            ('FONTSIZE', (0, 0), (-1, -1), self.config.font_size),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        
        return table
    
    def _create_summary_section(self, data: Dict[str, Any]) -> List:
        """Create summary section with statistics"""
        story = []
        story.append(Paragraph("Executive Summary", self.styles['CustomHeader']))
        
        # Use robust extraction to count records
        tracking_details = self._extract_tracking_records(data)
        total_count = len(tracking_details)

        # Try to get work area count from nonDeliveredTrackingCounts if present
        api_data = data.get('data', data)  # handle both wrapped and unwrapped
        if isinstance(api_data, dict):
            inner = api_data.get('data', api_data)
            tracking_counts = inner.get('nonDeliveredTrackingCounts', []) if isinstance(inner, dict) else []
        else:
            tracking_counts = []
        work_areas_count = len(tracking_counts)
        
        summary_data = [
            ['Metric', 'Value'],
            ['Total Non-Delivered Packages', str(total_count)],
            ['Unique Work Areas', str(work_areas_count)],
            ['Report Status', data.get('status', 'N/A').upper()],
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(self.config.header_color)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), f'{self.config.font_name}-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), self.config.font_name),
            ('FONTSIZE', (0, 1), (-1, -1), self.config.font_size),
        ]))
        
        story.append(summary_table)
        return story
    
    @staticmethod
    def _prettify_key(key: str) -> str:
        """Convert camelCase / snake_case / kebab-case key into Title Case words.
        e.g. 'workAreaName' -> 'Work Area Name', 'reason_code' -> 'Reason Code'
        """
        # Insert space before uppercase letter that follows a lowercase letter/digit
        spaced = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', key)
        # Handle consecutive uppercase + lowercase: 'IDCard' -> 'ID Card'
        spaced = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', spaced)
        # Replace underscores/hyphens with space
        spaced = spaced.replace('_', ' ').replace('-', ' ')
        # Collapse spaces and title-case each word
        return ' '.join(word.capitalize() for word in spaced.split())

    @staticmethod
    def _flatten_value(value: Any) -> str:
        """Convert any value to a readable string, flattening nested dicts/lists."""
        if value is None or value == '':
            return '-'
        if isinstance(value, dict):
            # Flatten one level: "key1: v1 | key2: v2"
            parts = [f"{k}: {v}" for k, v in value.items() if v is not None and v != '']
            return ' | '.join(parts) if parts else '-'
        if isinstance(value, list):
            return ', '.join(str(i) for i in value) if value else '-'
        return str(value)

    def _extract_tracking_records(self, data: Dict[str, Any]) -> List[Dict]:
        """
        Extract the list of tracking record dicts walking a deterministic path:
        1. Follow priority keys in order (most-specific first).
        2. Fall back to 'data' key.
        3. Last resort: return the largest list-of-dicts among all values.
        """
        # Priority keys to follow at each level, most-specific first
        PRIORITY_KEYS = (
            'nonDeliveredTrackingDetails',
            'trackingDetails',
            'details',
            'records',
            'items',
            'results',
        )

        node = data
        for _ in range(8):  # max depth
            if isinstance(node, list):
                # We've arrived at a list – return it if it contains dicts
                if node and isinstance(node[0], dict):
                    return node
                return []

            if not isinstance(node, dict):
                return []

            # Try priority keys first (most-specific wins)
            matched = False
            for key in PRIORITY_KEYS:
                if key in node:
                    node = node[key]
                    matched = True
                    break

            if not matched:
                # Try generic 'data' wrapper
                if 'data' in node:
                    node = node['data']
                else:
                    # Last resort: pick the largest list-of-dicts among all values
                    best: List[Dict] = []
                    for val in node.values():
                        if (isinstance(val, list) and
                                len(val) > len(best) and
                                val and isinstance(val[0], dict)):
                            best = val
                    return best

        return []

    def _create_tracking_table(self, data: Dict[str, Any]) -> Table:
        """Create main tracking data table"""
        tracking_data = self._extract_tracking_records(data)

        if not tracking_data or not isinstance(tracking_data, list):
            # No data available
            no_data = [['No tracking data available']]
            table = Table(no_data)
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), self.config.font_name),
                ('FONTSIZE', (0, 0), (-1, -1), self.config.font_size),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.red),
            ]))
            return table
        
        # Column mapping with display names and field names
        column_mapping = {
            'trackingId': 'Tracking ID',
            'deliveryRecordNumber': 'Delivery Record',
            'addressLine1': 'Address',
            'cityName': 'City',
            'stateCode': 'State',
            'postalCode': 'Zip',
            'reasonCode': 'Reason Code',
            'workAreaName': 'Work Area'
        }
        
        # Determine columns: use config.columns if specified, else auto-detect all from data
        if self.config.columns:
            active_columns = self.config.columns
        else:
            # Collect all unique keys from the entire dataset
            seen = {}
            for item in tracking_data:
                if isinstance(item, dict):
                    for key in item.keys():
                        if key not in seen:
                            seen[key] = True
            active_columns = list(seen.keys())
        
        # Prepare table data with selected columns based on config
        table_data = []
        
        # Build headers — use TableHeader style (white bold) so color shows correctly in Paragraph cells
        headers = []
        for col in active_columns:
            display = column_mapping.get(col) or self._prettify_key(col)
            headers.append(Paragraph(display, self.styles['TableHeader']))
        table_data.append(headers)

        # Limit records if max_records is specified
        records_to_process = tracking_data
        if self.config.max_records and self.config.max_records > 0:
            records_to_process = tracking_data[:self.config.max_records]

        # Add data rows — truncate per column type to keep rows compact
        # Limits chosen so values fit within the weighted column widths
        TRUNCATE = {
            'trackingId': 22,
            'deliveryRecordNumber': 18,
            'addressLine1': 28,
            'cityName': 15,
            'stateCode': 5,
            'postalCode': 8,
            'reasonCode': 12,
            'workAreaName': 14,
        }
        DEFAULT_TRUNCATE = 80  # generous default; wordWrap handles layout

        for item in records_to_process:
            if isinstance(item, dict):
                row = []
                for col in active_columns:
                    raw = item.get(col, None)
                    str_value = self._flatten_value(raw)
                    limit = TRUNCATE.get(col, DEFAULT_TRUNCATE)
                    if len(str_value) > limit:
                        str_value = str_value[:limit] + '…'
                    row.append(Paragraph(str_value, self.styles['TableCell']))
                table_data.append(row)

        # Smart column widths: known-wide columns get more space
        WIDE_COLS   = {'trackingId', 'addressLine1', 'deliveryRecordNumber'}
        NARROW_COLS = {'stateCode', 'postalCode', 'reasonCode'}

        num_cols = len(active_columns)
        page_w = self.config.page_size[0]   # already accounts for landscape (rotated in _get_page_size)

        left_margin  = 0.75 * inch
        right_margin = 0.75 * inch
        available_width = page_w - left_margin - right_margin

        # Assign relative weights: wide=2, normal=1.5, narrow=1
        weights = []
        for col in active_columns:
            if col in WIDE_COLS:
                weights.append(2.0)
            elif col in NARROW_COLS:
                weights.append(1.0)
            else:
                weights.append(1.5)
        total_weight = sum(weights)
        col_widths = [(w / total_weight) * available_width for w in weights]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            # Header row background (text color is in the Paragraph style itself)
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(self.config.header_color)),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),

            # Alternating row backgrounds
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F8')]),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))

        return table


def generate_pdf_report(
    data: Dict[str, Any],
    output_path: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    config: Optional[PDFReportConfig] = None
) -> bytes:
    """
    Convenience function to generate PDF report
    
    Args:
        data: Tracking data dictionary
        output_path: Optional file path to save PDF
        metadata: Optional metadata for report
        config: Optional PDF configuration
    
    Returns:
        PDF as bytes (if output_path is None)
    """
    generator = FedExPDFGenerator(config)
    return generator.generate_report(data, output_path, metadata)
