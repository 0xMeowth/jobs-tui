// ---- knobs: change these numbers, nothing below them ----
#let knob(name, default) = eval(sys.inputs.at(name, default: default))
#let font-name   = sys.inputs.at("font", default: "Nunito")
#let body-size   = knob("body_size", "9.5pt")
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
    text(weight: "bold", e.dates),
  ))
  #if "title" in e [#e.title \ ]
  #if "bullets" in e { bullets(e.bullets) }
]

#text(size: 27pt, tracking: 4pt, upper(data.name))
#v(1pt)
#data.contact.phone | #data.contact.email | #data.contact.linkedin

#for s in data.sections {
  section(s.title)
  if "entries" in s { for e in s.entries { entry(e) } }
  if "bullets" in s { bullets(s.bullets) }
}
