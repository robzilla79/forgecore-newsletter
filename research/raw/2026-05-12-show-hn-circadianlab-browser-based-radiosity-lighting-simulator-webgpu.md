# Show HN: CircadianLab – Browser-based radiosity lighting simulator (WebGPU)

- Source: Hacker News Show HN
- Published: Tue, 12 May 2026 16:35:58 +0000
- URL: https://www.innerscene.com/tools/circadian-lab
- Domain: innerscene.com
- Tags: builders, tools, indie

## Feed summary

We built CircadianLab, a free in-browser tool for lighting design. It uses webGPU shaders to calculate melanopic equivalent daylight illuminance (mel-EDI, formerly EML, relevant for circadian rhythm and WELL v2 compliance), photopic illuminance, UGR glare per CIE 117, and actual daylight through windows and skylights.It has a database of 400,000+ IES files from 81 lighting manufacturers and supports easy sharing of scenes/configs with other people.Daylight uses the NREL Solar Position Algorithm and a Perez clear / intermediate / overcast sky model, mixed into the same radiosity solve as electric fixtures. Sun and sky are added as initial flux on every patch, then bounced through the same form-factor network.  Form factors via Monte Carlo with visibility tests, then a Gauss-Seidel 3-bounce iterative solve.  My company (Innerscene) makes "daylight" luminaires. We built CircadianLab to address a specific gap (no browser-based way to verify WELL v2 mel-EDI compliance before specifying), but it works with any IES file from any manufacturer, not just our line.  For mel-EDI you need SPDs to accurately calculate but CCT is a good proxy.

  Write-up + demo videos: https://www.innerscene.com/blog/introducing-circadian-lab

Of interest to HN crowd, there are measurable productivity/performance enhancements that can be achieved with higher mel-EDIs which is why the design community is now 

## Extracted article text

CircadianLab — EML, Illuminance & Glare Calculator
CircadianLab is a free lighting analysis tool that calculates four key metrics: melanopic equivalent lux (EML) for circadian lighting design, illuminance in lux and foot-candles for general lighting analysis, UGR (Unified Glare Rating) for visual comfort assessment, and daylight through windows and skylights using NREL solar-position physics and a Perez sky model. Daylight and electric light are solved together in a single unified radiosity pass, so heatmaps reflect realistic combined illuminance from all sources.
Use it to design lighting layouts that meet WELL v2 Feature L03 requirements, verify illuminance levels against IES/CIE standards, evaluate glare comfort per CIE 117:1995, study daylight at any date, time, and location, compare fixture options, and generate professional reports — all in your browser with no signup required.
What is EML and Why Does It Matter?
Traditional lighting design focuses on photopic illuminance (lux) — how bright a space appears to the human visual system. But the non-visual effects of light on circadian rhythms depend on a different metric: melanopic equivalent daylight illuminance.
EML is calculated as: EML = Illuminance (lux) × Melanopic DER
The melanopic Daylight Equivalent Ratio (DER) depends on the spectral power distribution of the light source and varies with color temperature (CCT). At 6,000K (daylight), the DER is 1.0 by definition. Warm LEDs (2,700K) have a DER of ~0.44, meaning they produce less than half the melanopic stimulation per lux compared to daylight. High-CCT sources like Innerscene Circadian Sky at 200,000K achieve DER values of ~1.89.
WELL v2 Feature L03 — Circadian Lighting Design
The WELL Building Standard v2 requires spaces to provide adequate melanopic light at eye level for occupant health and wellbeing:
- Tier 1: ≥150 melanopic EDI in at least one vertical direction at 1.2m (seated eye height)
- Tier 2: ≥275 melanopic EDI in at least one vertical direction at 1.2m
This calculator checks compliance at every measurement grid point and reports the percentage that passes each tier. The vertical-direction requirement means ceiling-mounted downlights alone often fall short — wall-mounted fixtures at eye level can be far more effective for melanopic stimulation.
How the Simulation Works
Direct Illuminance
Each fixture's intensity toward every measurement point is computed using IES Type C photometry with inverse-square law attenuation and cosine incidence correction. Area sources use 12×12 subdivision integration.
Radiosity (Indirect Light)
A 3-bounce iterative radiosity solver computes form factors between all surface patches, then solves for inter-reflected light. This captures how walls, floors, and ceilings redirect light throughout the space.
Melanopic Conversion
Photopic illuminance is converted to EML using measured melanopic DER values. For Circadian Sky fixtures, a 22-point lookup table from real spectral measurements is used. Custom DER values can be provided for any fixture.
Directional Measurement
EML is computed in 5 directions at each grid point: horizontal (desk level) plus the 4 cardinal vertical directions (north, east, south, west) at eye height. WELL compliance requires only one vertical direction to pass.
Daylight Through Windows
Sun position uses the NREL Solar Position Algorithm; sky brightness uses a Perez clear/intermediate/overcast model. For each window aperture, direct sun and diffuse sky illuminance are added as initial flux on every radiosity patch and measurement point and bounced through the same form-factor network as the fixtures — daylight and electric light share one solve.
Validated Calculations
Every calculation in this tool is verified by an automated validation suite — 120+ tests covering inverse-square law, cosine incidence, radiosity energy conservation, IES lumen integration, melanopic DER accuracy, and WELL v2 compliance logic. Tests run against 20 IES photometric files from 8 manufacturers including BEGA, Philips, American Electric Lighting, and Innerscene.
Features
IES Photometry
Load real measured photometric data from IES files for accurate light distribution modeling
Circadian Sky Presets
All 5 Innerscene Circadian Sky sizes with measured melanopic DER data
Wall Fixtures
Mount fixtures on any wall with height and tilt control for eye-level melanopic stimulation
WELL Compliance
Automatic Tier 1/2 checking at every grid point with pass/fail statistics
CCT Control
2,200K to 200,000K with real-time EML recalculation using variable melanopic DER
PDF Reports
Professional reports with heatmaps for all directions, fixture schedule, and QR code
Share Links
Save and share your exact session — room, fixtures, camera angle, and results
Custom IES Upload
Upload any IES file with custom melanopic DER for third-party fixtures
3D Visualization
Interactive 3D room view with orbit controls, heatmap texture, and occupant models
Ceiling Grid Snap
Rotatable ceiling grid with fixture snap alignment for precise troffer placement
Illuminance (Lux/FC)
Calculate horizontal and directional illuminance in lux or foot-candles with inverse-square law and IES photometry
UGR Glare Analysis
Unified Glare Rating per CIE 117:1995 with directional heatmaps, Guth position index, and per-occupant evaluation
Floor Illuminance
Separate floor-level analysis for emergency egress and ambient light distribution
Daylight + Skylights
Add wall windows and skylights with configurable glazing; sun + sky at any date, time, and lat/lon are solved with the same radiosity engine as the electric fixtures
Lighting Term Glossary(78 terms — click to expand)
- Airmass
- The relative thickness of atmosphere the sun's beam passes through, approximately 1/sin(altitude). Airmass 1 = sun overhead; airmass 18 = sun about 2.5° above the horizon. Drives the attenuation of direct sun illuminance near sunrise and sunset.
- ANSI/IES RP-46-25
- 2025 recommended practice from the Illuminating Engineering Society for lighting's circadian, neuroendocrine, and neurobehavioral effects. Calls for a daytime minimum of 250 mel-EDI at the eye. Newer than the WELL Building Standard and increasingly cited by specifiers.
- Artificial skylight
- A luminaire that simulates a real skylight, typically combining a directional sun beam with a diffuse sky luminance and a depth illusion. Innerscene Virtual Sun is an example.
- Artificial window
- A luminaire that simulates a real window in a wall, providing a virtual exterior view in addition to circadian-active light.
- ATMOS
- Innerscene's 4-chip LED platform underlying the Circadian Sky product line. Enables a 2,200K–200,000K tunable CCT range while holding CRI ≥ 91 across the entire range.
- Ballast factor
- Multiplier in an IES file that scales reported candela values to account for the actual driver or ballast. CircadianLab applies the ballast factor when reading IES photometry.
- Beam angle
- The cone angle within which a directional luminaire's 
