// ---- knobs: change these numbers, nothing below them ----
#let knob(name, default) = eval(sys.inputs.at(name, default: default))
#let font-name   = sys.inputs.at("font", default: "Nunito")
#let body-size   = knob("body_size", "10pt")
#let leading     = knob("leading", "0.7em")     // space between lines
#let section-gap = knob("section_gap", "14pt")  // space above a section bar
#let entry-gap   = knob("entry_gap", "16pt")  // space above each job
#let margin-x    = knob("margin_x", "1cm")
#let margin-y    = knob("margin_y", "1.2cm")
// ---------------------------------------------------------

#let data = yaml(sys.inputs.resume)
#let ink = rgb("#212121")

#set page(paper: "a4", margin: (x: margin-x, y: margin-y))
#set text(font: font-name, size: body-size, fill: ink)
#set par(leading: leading, justify: false)
#set list(marker: text(weight: "bold")[•], indent: 0pt, body-indent: 5pt, spacing: leading)

#let section(title) = block(
  width: 100%, fill: luma(235), inset: (x: 5pt, y: 3pt),
  above: section-gap, below: 5pt,
  text(weight: "bold", size: 11.5pt, tracking: 1pt, upper(title)),
)

#let bullets(items) = list(..items.map(b => b.text))

#let entry(e) = block(breakable: false, above: entry-gap, below: 0pt)[
  #block(below: 0.35em, grid(
    columns: (1fr, auto), column-gutter: 8pt,
    text(weight: "bold", e.org),
    if "dates" in e { text(weight: "bold", e.dates) } else { none },
  ))
  #if "url" in e [#link("https://" + e.url)[#e.url] \ ]
  #if "title" in e [#e.title \ ]
  #if "bullets" in e { bullets(e.bullets) }
]

#text(size: 27pt, tracking: 1.5pt, data.name)
#v(1pt)
#{ ("location", "phone", "email", "linkedin").filter(k => k in data.contact).map(k => data.contact.at(k)).join(" | ") }

#for s in data.sections {
  section(s.title)
  if "entries" in s { for e in s.entries { entry(e) } }
  if "bullets" in s { bullets(s.bullets) }
}
