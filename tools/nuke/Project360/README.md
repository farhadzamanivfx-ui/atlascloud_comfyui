# Project360 — نود پروجکشن ۳۶۰ برای Nuke

یک نود Material برای سیستم 3D کلاسیک Nuke که تصویر LatLong را مثل نرم‌افزارهای 3D (Maya، Blender، Houdini) پروجکت می‌کند. از ماتریس ۴×۴ و دوربین spherical استفاده نمی‌کند، پس باگ‌های Project3D را ندارد.

## الگوریتم

برای هر نقطه‌ای از سطح که رندر می‌شود (`P` در فضای جهانی):

```
d = inverse(cam world matrix) * P          # جهت از پروجکتور در فضای محلی آن
u = 0.5 + atan2(d.x, -d.z) / 2π  (+ heading/360، و در صورت mirror: 1 - u)
v = 0.5 + asin(d.y / |d|) / π
color = sample(img, u, v)
```

این همان فرمول صفحه‌ی ۳ PDF است، با این تفاوت که داخل شیدر و به‌ازای هر نقطه اجرا می‌شود؛ نه پاس P و STMap دوبعدی. فیلتر تکسچر از مشتق‌های صفحه حساب می‌شود و درز `u = 0/1` را درست رد می‌کند. فاصله‌ی گنبد مهم نیست (Near/Far ندارد) و پشت دوربین هم پروجکت می‌شود.

## ورودی‌ها و knobها

| | |
|---|---|
| `img` | تصویر LatLong (۲:۱) |
| `cam` | هر Camera یا Axis؛ فقط ماتریس جهانی‌اش استفاده می‌شود (داخل FBX هم درست است) |
| `heading (deg)` | چرخش پانوراما حول محور عمودی |
| `mirror horizontally` | آینه‌ی چپ و راست |
| `use camera rotation` | روشن: پانوراما با چرخش دوربین می‌چرخد. خاموش: فقط موقعیت دوربین؛ ‎-Z‎ جهانی وسط تصویر است |
| `set alpha to 1` | فایل HDR معمولاً alpha ندارد؛ با این گزینه کل پروجکشن opaque است |
| `filter` | فیلتر نمونه‌برداری (پیش‌فرض Cubic) |

## نحوه‌ی استفاده (Dome → UV Bake)

```
Read (DH210SX.hdr) ──img──┐
Camera1 ─────────────cam──┤
                     Project360 ──img──> ReadGeo1 (گنبد)
                                            │
Constant 4096×4096 ──bg──> ScanlineRender (projection mode = uv) ──> Write (EXR)
```

1. `Project360` را بساز. HDR را به `img` و `Camera1` را به `cam` وصل کن.
2. خروجی آن را به ورودی `img` در `ReadGeo1` بده (یا از `ApplyMaterial` استفاده کن).
3. برای bake: `ScanlineRender` با `projection mode = uv` و یک bg مربعی ۴۰۹۶ بساز → Write.
4. برای دیدن نتیجه: یک `ScanlineRender` معمولی با هر دوربین دلخواه بساز و در ویوئر 2D نگاه کن.

ویوپورت OpenGL فقط نگاشت خطی تکسچر را بلد است. برای همین این نود در ویوپورت 3D گنبد را بدون تکسچر نشان می‌دهد. برای دیدن تکسچر در ویوپورت، فایل bake شده را Read کن و به گنبد بده.

## Build

این یک پلاگین C++ (NDK) است و باید برای **همان نسخه‌ی Nuke** که استفاده می‌کنی build شود. هدرهای NDK همراه خود Nuke نصب می‌شوند (پوشه‌ی `include` در محل نصب).

### Windows

پیش‌نیاز: Visual Studio با ابزار C++ و CMake. برای Nuke 13/14 از VS 2019 و برای Nuke 15+ از VS 2022 استفاده کن.

```bat
cd tools\nuke\Project360
cmake -B build -G "Visual Studio 17 2022" -A x64 -DNUKE_ROOT="C:/Program Files/Nuke15.1v3"
cmake --build build --config Release
```

فایل خروجی: `build\Release\Project360.dll`

### Linux

```bash
cd tools/nuke/Project360
cmake -B build -DCMAKE_BUILD_TYPE=Release -DNUKE_ROOT=/usr/local/Nuke15.1v3 -DNUKE_OLD_ABI=OFF   # Nuke 14 و قدیمی‌تر: ON
cmake --build build
```

### نصب

فایل `Project360.dll` (یا `.so`) را در `~/.nuke` (ویندوز: `%USERPROFILE%\.nuke`) کپی کن و این خط را به `menu.py` اضافه کن:

```python
nuke.menu("Nodes").addCommand("3D/Project360", "nuke.createNode('Project360')")
```

## تست

فرمول نگاشت در `Project360Math.h` جدا شده و بدون Nuke تست می‌شود:

```bash
g++ -std=c++17 test_project360_math.cpp -o test && ./test
```

## موارد تأییدنشده

کد با هدرهای واقعی NDK کامپایل نشده (Nuke در دسترس نبود). فقط فرمول تست شده و ساختار C++ با هدرهای شبیه‌سازی‌شده چک شده است. اگر build خطا داد، متن خطا را بفرست.

- [ ] نام توابع `VertexContext::dPWdx()/dPWdy()` و `AxisOp::imatrix()` در NDK نسخه‌ی تو
- [ ] ScanlineRender در حالت `uv` شیدر را با `PW` درست صدا می‌زند (Project3D همین کار را می‌کند، پس باید بزند)
- [ ] جهت u با مرجع UVProject یکی است (اگر نبود، `mirror` یا `heading` را تنظیم کن)
- [ ] RayRender هم با این material کار می‌کند
