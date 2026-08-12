import urllib.request
import json
import os
import re
import html as html_module

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
months = ['มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน','กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม']

def get_clean_text(html):
    clean = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.DOTALL)
    clean = re.sub(r'<style.*?>.*?</style>', '', clean, flags=re.DOTALL)
    clean = re.sub(r'<[^>]+>', '\n', clean)
    return html_module.unescape(clean)

def split_doc_into_date_blocks(clean_text, default_date='12 สิงหาคม 2026'):
    parts = re.split(r'\[อัปเดตล่าสุด:\s*(\d{1,2}/\d{1,2}/\d{4})\]', clean_text)
    if len(parts) <= 1:
        return [(default_date, clean_text)]
    
    blocks = []
    for i in range(1, len(parts), 2):
        date_str = parts[i]
        content = parts[i+1]
        dm = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_str)
        if dm:
            d, m, y = dm.groups()
            date_label = f"{int(d)} {months[int(m)-1]} {y}"
        else:
            date_label = date_str
        blocks.append((date_label, content))
    return blocks

# =========================================================================
# 1. PARSE ALL NEWS SLOTS
# =========================================================================
def parse_all_news(html):
    clean_text = get_clean_text(html)
    blocks = split_doc_into_date_blocks(clean_text, '12 สิงหาคม 2026')
    slots = []

    for date_label, block_text in blocks:
        lines = [l.strip() for l in block_text.splitlines() if l.strip()]
        current_company = None
        company_lines = {'arm': [], 'mu': []}

        for l in lines:
            if 'รายงานสรุปข้อมูลอัปเดต' in l:
                continue
            if re.search(r'^\d+\.\s*Arm', l, re.IGNORECASE) or 'Arm Holdings' in l:
                current_company = 'arm'
            elif re.search(r'^\d+\.\s*Micron', l, re.IGNORECASE) or 'Micron Technology' in l:
                current_company = 'mu'
            elif current_company:
                company_lines[current_company].append(l)

        sections = []
        for comp_id, comp_title in [('arm', '1. Arm Holdings plc (ARM)'), ('mu', '2. Micron Technology, Inc. (MU)')]:
            clines = company_lines.get(comp_id, [])
            highlights = []
            details = []

            for cl in clines:
                if ':' in cl:
                    parts = cl.split(':', 1)
                    k = parts[0].strip()
                    v = parts[1].strip()

                    val_match = re.search(r'(\$[\d\.,]+(?:\s*[MBKพันล้าน]+)?|[+-]?\d+(?:\.\d+)?%|Strong Buy|\d+(?:\.\d+)?\s*เท่า)', v)
                    if val_match and len(highlights) < 4:
                        val_str = val_match.group(1)
                        desc_str = v.replace(val_str, '').strip()
                        highlights.append({
                            'label': k,
                            'value': val_str,
                            'desc': desc_str if desc_str else v
                        })
                    else:
                        details.append(f"{k}: {v}")
                else:
                    if len(cl) > 5:
                        details.append(cl)

            if not highlights and details:
                for d in details[:3]:
                    if ':' in d:
                        dp = d.split(':', 1)
                        highlights.append({'label': dp[0].strip(), 'value': 'อัปเดต', 'desc': dp[1].strip()})

            sections.append({
                'id': comp_id,
                'title': comp_title,
                'subsections': [
                    {
                        'subtitle': f'ผลประกอบการและข่าวสารล่าสุด',
                        'highlights': highlights if highlights else [{'label': 'สถานะ', 'value': 'อัปเดตปกติ', 'desc': 'ข้อมูลประจำวัน'}]
                    },
                    {
                        'subtitle': f'ประเด็นสำคัญและผลกระทบเชิงกลยุทธ์',
                        'details': details if details else ['ติดตามความคืบหน้าของอุตสาหกรรมอย่างต่อเนื่อง']
                    }
                ]
            })

        slots.append({
            'slotId': f'news-{date_label}',
            'dateLabel': date_label,
            'title': 'รายงานสรุปข้อมูลอัปเดตข่าวสาร',
            'subtitle': f'Arm Holdings (ARM) & Micron Technology (MU) - ประจำวันที่ {date_label}',
            'sections': sections
        })

    return slots

# =========================================================================
# 2. PARSE ALL PORTFOLIO SLOTS
# =========================================================================
def parse_all_portfolio(html):
    clean_text = get_clean_text(html)
    blocks = split_doc_into_date_blocks(clean_text, '12 สิงหาคม 2026')
    slots = []

    for date_label, block_text in blocks:
        thb_m = re.search(r'มูลค่าพอร์ตรวม\s*:\s*([\d,]+\.\d{2})\s*THB', block_text)
        total_thb = thb_m.group(1) if thb_m else '21,668.41'

        usd_m = re.search(r'≈\s*(\$[\d,]+\.\d{2}\s*USD)', block_text)
        total_usd = usd_m.group(1) if usd_m else '$544.33 USD'

        us_m = re.search(r'หุ้นสหรัฐฯ\s*:\s*([\d\.]+\s*%)', block_text)
        us_share = us_m.group(1) if us_m else '84.23%'

        cash_m = re.search(r'เงินสด/สภาพคล่อง\s*:\s*([\d\.]+\s*%)', block_text)
        cash_share = cash_m.group(1) if cash_m else '15.77%'

        cash_thb_m = re.search(r'เงินสด/สภาพคล่อง\s*:\s*[\d\.]+\s*%\s*\(([\d,]+\.\d{2}\s*THB)\)', block_text)
        cash_thb = cash_thb_m.group(1) if cash_thb_m else '3,417.14 THB'

        pl_m = re.search(r'ผลตอบแทนรวม\s*:\s*([+-]?[\d\.]+\s*%)', block_text)
        unrealized_pl = pl_m.group(1) if pl_m else '-18.83%'

        slots.append({
            'slotId': f'port-{date_label}',
            'dateLabel': date_label,
            'totalThb': total_thb,
            'totalUsd': total_usd,
            'unrealizedPl': unrealized_pl,
            'usStocksShare': us_share,
            'cashShare': cash_share,
            'cashThb': cash_thb,
            'historyFilterData': {
                '1W': [22500, 22200, 21900, 21500, 21800, 21700, 21668],
                '1M': [25000, 24500, 24000, 23500, 23000, 22500, 22000, 21500, 21800, 21668],
                'YTD': [20000, 21000, 23000, 24000, 25500, 24500, 23000, 21668]
            },
            'holdings': [
                {'ticker': 'ARM Holdings (ARM)', 'desc': 'ผู้นำสถาปัตยกรรมชิป AI & Data Center', 'share': '78.60%', 'avgCost': '$286.63', 'price': '$224.89', 'pl': '-21.54%'},
                {'ticker': 'Micron Technology (MU)', 'desc': 'ผู้ผลิตหน่วยความจำ HBM / DRAM ยุค AI', 'share': '21.40%', 'avgCost': '$794.99', 'price': '$739.00', 'pl': '-7.04%'}
            ]
        })

    return slots

# =========================================================================
# 3. PARSE ALL REPORT SLOTS
# =========================================================================
def parse_all_report(html):
    clean_text = get_clean_text(html)
    blocks = split_doc_into_date_blocks(clean_text, '12 สิงหาคม 2026')
    slots = []

    for date_label, block_text in blocks:
        slots.append({
            'slotId': f'report-{date_label}',
            'dateLabel': date_label,
            'title': 'รายงานวิเคราะห์ AI & Arm Holdings',
            'subtitle': f'ประจำสัปดาห์ ({date_label})',
            'section1': {
                'title': '1. สรุปอัปเดตข่าวและงบการเงิน Arm Holdings (ARM)',
                'intro': 'อัปเดตงบการเงินไตรมาส Q1 FYE27 และการวิเคราะห์รายสัปดาห์ล่าสุด:',
                'highlights': [
                    {'label': 'รายได้รวม (Total Revenue)', 'value': '$1.289 พันล้าน', 'desc': '(+22% YoY) ทำสถิติสูงสุดใหม่สำหรับ Q1'},
                    {'label': 'กำไรสุทธิปรับปรุง (Non-GAAP EPS)', 'value': '$0.45', 'desc': '(+29% YoY) สูงกว่ากรอบเป้าหมาย'},
                    {'label': 'Royalty Revenue', 'value': '$715 ล้าน', 'desc': '(+22% YoY) ทำสถิติ Q1 สูงสุด'},
                    {'label': 'Licensing Revenue', 'value': '$574 ล้าน', 'desc': '(+23% YoY) เติบโตแข็งแกร่ง'}
                ],
                'details': [
                    'Data Center Royalty: พุ่งขึ้นสถิติใหม่ เติบโตเกินกว่าเท่าตัว (>100% YoY) จากชิป Neoverse ใน Hyperscalers',
                    'ปฏิกิริยาราคาหุ้น: หุ้นรีบาวด์ขึ้นแรง +6.5% ถึง +7.4% ปิดสัปดาห์ที่บริเวณ ~$240-$241 USD',
                    'NVIDIA & Arm Synergy: ชิป Grace & Vera CPU เชื่อมต่อผ่าน NVLink-C2C แบนด์วิดท์ 1.8 TB/s ปลดล็อกคอขวดระบบ AI',
                    'เป้าหมาย Valuation: แผน Value Creation Plan มุ่งสู่ Market Cap $1-$2 Trillion ภายในปี 2029-2031'
                ]
            },
            'section2': {
                'title': '2. ประเมินสถิติ Arm ตามกรอบ 5 Checkpoints',
                'checkpoints': [
                    {'id': 1, 'name': 'CSS Adoption & Royalty Expansion', 'status': 'ผ่าน', 'desc': 'รายได้ Royalty ทำสถิติ $715M (+22% YoY) ค่าสิทธิ์ขยับสู่ 5%-10% ต่อชิป'},
                    {'id': 2, 'name': 'Data Center & Cloud AI', 'status': 'ผ่านดีเยี่ยม', 'desc': 'รายได้ Royalty ฝั่ง Data Center เติบโตมากกว่า >100% YoY'},
                    {'id': 3, 'name': 'Armv9 Penetration', 'status': 'ผ่าน', 'desc': 'สัดส่วนรายได้จาก Armv9 เพิ่มขึ้นเกิน >30%-35% ของ Royalty รวม'},
                    {'id': 4, 'name': 'Margins & Cash Flow', 'status': 'ผ่านดีเยี่ยม', 'desc': 'Gross Margin 95%-98%, โมเดล Asset-Light ไม่มีภาระสร้าง Fab'},
                    {'id': 5, 'name': 'Guidance & Risks', 'status': 'เฝ้าระวัง', 'desc': 'ติดตามการแข่งขันจาก RISC-V และคดีความ Qualcomm vs. Arm'}
                ]
            },
            'section3': {
                'title': '3. คัดสรรหุ้น AI ที่น่าสนใจประจำสัปดาห์ (Top AI Stock Picks)',
                'picks': [
                    {'ticker': 'MU', 'name': 'Micron Technology', 'phase': 'Phase 2: Hardware & Memory', 'reason': 'ราคาหุ้นรีบาวด์พุ่งขึ้นแรง ได้รับประโยชน์สูงสุดจากอุปสงค์ HBM และ DRAM ขาดแคลน'},
                    {'ticker': 'NVDA', 'name': 'NVIDIA', 'phase': 'Phase 1: Core AI Enablers', 'reason': 'ผู้นำระบบ AI เต็มรูปแบบ Grace/Vera Rubin สถาปัตยกรรม Blackwell ขยายตัวต่อเนื่อง'},
                    {'ticker': 'GOOGL', 'name': 'Alphabet', 'phase': 'Phase 3: Cloud Hyperscaler', 'reason': 'Google Axion N4A ชิป Arm ประสิทธิภาพสูง Cloud โตแรง Valuation P/E น่าดึงดูด'}
                ]
            }
        })

    return slots

# =========================================================================
# MAIN EXECUTION
# =========================================================================
docs_config = {
    'news': ('https://docs.google.com/document/d/1WKpJ23Rat0qBIF5flz11xRkR7s26x2W5fiBhc6lz7Ww/mobilebasic', 'doc_news.html', 'news_slots.json', parse_all_news),
    'portfolio': ('https://docs.google.com/document/d/1Dbrad52p9vrD5JYNqdzphmaHT58bx33p4KV8wbKUg2E/mobilebasic', 'doc_portfolio.html', 'portfolio_slots.json', parse_all_portfolio),
    'report': ('https://docs.google.com/document/d/12z-gUI6mbkJodbjBdLAiPoOBbHS3ooJ8hyf1J0yTC7k/mobilebasic', 'doc_report.html', 'report_slots.json', parse_all_report)
}

if __name__ == '__main__':
    for cat, (url, html_file, json_file, parser_fn) in docs_config.items():
        print(f"\nProcessing {cat} from {url}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as res:
                content = res.read().decode('utf-8')
            
            if len(content.strip()) > 500:
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(content)

                slots = parser_fn(content)
                print(f"-> Generated {len(slots)} slots for {cat}")

                # Purge invalid corrupted slots
                valid_slots = [
                    s for s in slots 
                    if '00 ล้านดอลลาร์' not in str(s.get('dateLabel', ''))
                    and 'ตลาดจะตึงตัว' not in str(s.get('dateLabel', ''))
                ]

                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(valid_slots, f, ensure_ascii=False, indent=2)

                print(f"-> Successfully saved {len(valid_slots)} slots to {json_file}")
            else:
                print(f"-> Failed: content too short")
        except Exception as e:
            print(f"-> Error: {e}")
