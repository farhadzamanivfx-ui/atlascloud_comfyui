# Nuke Dome Projection — Cube Rig (فقط پروجکشن سه‌بعدی)

جایگزین روش `P + STMap` برای پروژه‌ی `COP31_DOME_PROJECTION`. هیچ STMap، پاس P یا اکسپرشن پیکسلی ندارد؛ همه‌چیز با نودهای 3D خود Nuke انجام می‌شود.

## ایده

`Project3D` فقط با ماتریس ۴×۴ کار می‌کند و LatLong را نمی‌شود با یک ماتریس ساخت؛ دوربین spherical هم با ScanlineRender باگ دارد.
ولی یک پانورامای ۳۶۰ دقیقاً معادل **شش دوربین perspective با زاویه‌ی ۹۰ درجه** (یک کیوب‌مپ) در همان نقطه است. پس دوربین spherical را با شش دوربین عادی عوض می‌کنیم:

1. **Sphere** با HDR تکسچر می‌شود (UV خود Sphere در Nuke همان LatLong است) و در موقعیت `Camera1` قرار می‌گیرد.
2. **شش دوربین** (±X، ±Y، ±Z) با FOV = 92° در موقعیت `Camera1`، داخل کره را رندر می‌کنند → شش وجه کیوب.
3. **شش Project3D** همان وجه‌ها را از همان شش دوربین روی گنبد پروجکت می‌کنند (`crop` روشن).
4. **MergeMat (over)** شش پروجکشن را روی هم می‌گذارد → **ApplyMaterial** روی `ReadGeo1`.
5. **ScanlineRender** در حالت `projection mode = uv` گنبد را در فضای UV اصلی bake می‌کند → **Write** EXR.

همپوشانی ۲ درجه‌ای لبه‌ها پیکسل‌های یکسان دارد، پس درز ندیده می‌شود. چون Project3D (برخلاف UVProject) UV را عوض نمی‌کند، bake در حالت uv درست کار می‌کند.

## اجرا

1. در Node Graph سه نود را انتخاب کن: `Camera1`، `ReadGeo1`، `Read` مربوط به HDR.
2. در Script Editor:

   ```python
   exec(open(r"N:/JOBS/COP31_DOME_PROJECTION/_Temp/Farhad/cube_projection_bake.py").read())
   ```

3. پیام `Built.` یعنی موفق؛ هر `WARNING` یعنی یک knob یا ورودی پیدا نشد و باید دستی تنظیم شود.
4. روی `CubeBake_Write` مسیر بده و رندر بگیر. همه‌ی نودها با یک Ctrl+Z پاک می‌شوند.

## تنظیم جهت

در نود `CubeBake_Controls` (تب Cube Bake):

- `heading (deg)`: چرخش پانوراما حول محور عمودی.
- `mirror horizontally`: پیش‌فرض روشن، چون LatLong از داخل Sphere آینه دیده می‌شود. با نتیجه‌ی UVProject مقایسه کن؛ اگر برعکس بود خاموشش کن.

## تنظیمات بالای اسکریپت

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `UV_SIZE` | 4096 | رزولوشن تکسچر خروجی |
| `FACE_SIZE` | 2048 | رزولوشن هر وجه کیوب (برای HDR 6260 پیکسلی کافی است) |
| `FACE_FOV` | 92 | زاویه‌ی هر دوربین؛ بالای ۹۰ برای همپوشانی |
| `SPHERE_SEGMENTS` | 128 × 256 | تراکم کره؛ کمتر یعنی کمی اعوجاج روی وجه‌ها |

## دیدن نتیجه در 3D

- **زنده:** خروجی `CubeBake_ApplyMaterial` را در ویوپورت 3D (Tab) ببین. برای سبک‌تر شدن، `FACE_SIZE` را موقتاً ۵۱۲ کن.
- **سبک‌ترین:** فایل bake شده را Read کن و به ورودی `img` یک کپی از ReadGeo1 بده (`display = textured`).

## موارد تأییدنشده

اسکریپت روی Nuke واقعی تست نشده؛ این‌ها را چک کن:

- [ ] `Camera1.world_matrix.3/.7/.11` همان موقعیت جهانی دوربین است.
- [ ] نام knobهای `project_on`، `occlusion_mode`، `crop` روی Project3D نسخه‌ی تو.
- [ ] جهت mirror/heading با مرجع UVProject یکی است.
- [ ] اگر گنبد جزئیات داخلی دارد که روی هم سایه می‌اندازند، `occlusion_mode` را روی `self` بگذار.
