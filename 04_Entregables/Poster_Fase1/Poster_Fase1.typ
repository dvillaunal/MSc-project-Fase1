// Simple numbering for non-book documents
#let equation-numbering = "(1)"
#let callout-numbering = "1"
#let subfloat-numbering(n-super, subfloat-idx) = {
  numbering("1a", n-super, subfloat-idx)
}

// Theorem configuration for theorion
// Simple numbering for non-book documents (no heading inheritance)
#let theorem-inherited-levels = 0

// Theorem numbering format (can be overridden by extensions for appendix support)
// This function returns the numbering pattern to use
#let theorem-numbering(loc) = "1.1"

// Default theorem render function
#let theorem-render(prefix: none, title: "", full-title: auto, body) = {
  if full-title != "" and full-title != auto and full-title != none {
    strong[#full-title.]
    h(0.5em)
  }
  body
}
// Some definitions presupposed by pandoc's typst output.
#let content-to-string(content) = {
  if content.has("text") {
    content.text
  } else if content.has("children") {
    content.children.map(content-to-string).join("")
  } else if content.has("body") {
    content-to-string(content.body)
  } else if content == [ ] {
    " "
  }
}

#let horizontalrule = line(start: (25%,0%), end: (75%,0%))

#let endnote(num, contents) = [
  #stack(dir: ltr, spacing: 3pt, super[#num], contents)
]

#show terms.item: it => block(breakable: false)[
  #text(weight: "bold")[#it.term]
  #block(inset: (left: 1.5em, top: -0.4em))[#it.description]
]

// Some quarto-specific definitions.

#show raw.where(block: true): set block(
    fill: luma(230),
    width: 100%,
    inset: 8pt,
    radius: 2pt
  )

#let block_with_new_content(old_block, new_content) = {
  let fields = old_block.fields()
  let _ = fields.remove("body")
  if fields.at("below", default: none) != none {
    // TODO: this is a hack because below is a "synthesized element"
    // according to the experts in the typst discord...
    fields.below = fields.below.abs
  }
  block.with(..fields)(new_content)
}

#let empty(v) = {
  if type(v) == str {
    // two dollar signs here because we're technically inside
    // a Pandoc template :grimace:
    v.matches(regex("^\\s*$")).at(0, default: none) != none
  } else if type(v) == content {
    if v.at("text", default: none) != none {
      return empty(v.text)
    }
    for child in v.at("children", default: ()) {
      if not empty(child) {
        return false
      }
    }
    return true
  }

}

// Subfloats
// This is a technique that we adapted from https://github.com/tingerrr/subpar/
#let quartosubfloatcounter = counter("quartosubfloatcounter")

#let quarto_super(
  kind: str,
  caption: none,
  label: none,
  supplement: str,
  position: none,
  subcapnumbering: "(a)",
  body,
) = {
  context {
    let figcounter = counter(figure.where(kind: kind))
    let n-super = figcounter.get().first() + 1
    set figure.caption(position: position)
    [#figure(
      kind: kind,
      supplement: supplement,
      caption: caption,
      {
        show figure.where(kind: kind): set figure(numbering: _ => {
          let subfloat-idx = quartosubfloatcounter.get().first() + 1
          subfloat-numbering(n-super, subfloat-idx)
        })
        show figure.where(kind: kind): set figure.caption(position: position)

        show figure: it => {
          let num = numbering(subcapnumbering, n-super, quartosubfloatcounter.get().first() + 1)
          show figure.caption: it => block({
            num.slice(2) // I don't understand why the numbering contains output that it really shouldn't, but this fixes it shrug?
            [ ]
            it.body
          })

          quartosubfloatcounter.step()
          it
          counter(figure.where(kind: it.kind)).update(n => n - 1)
        }

        quartosubfloatcounter.update(0)
        body
      }
    )#label]
  }
}

// callout rendering
// this is a figure show rule because callouts are crossreferenceable
#show figure: it => {
  if type(it.kind) != str {
    return it
  }
  let kind_match = it.kind.matches(regex("^quarto-callout-(.*)")).at(0, default: none)
  if kind_match == none {
    return it
  }
  let kind = kind_match.captures.at(0, default: "other")
  kind = upper(kind.first()) + kind.slice(1)
  // now we pull apart the callout and reassemble it with the crossref name and counter

  // when we cleanup pandoc's emitted code to avoid spaces this will have to change
  let old_callout = it.body.children.at(1).body.children.at(1)
  let old_title_block = old_callout.body.children.at(0)
  let children = old_title_block.body.body.children
  let old_title = if children.len() == 1 {
    children.at(0)  // no icon: title at index 0
  } else {
    children.at(1)  // with icon: title at index 1
  }

  // TODO use custom separator if available
  // Use the figure's counter display which handles chapter-based numbering
  // (when numbering is a function that includes the heading counter)
  let callout_num = it.counter.display(it.numbering)
  let new_title = if empty(old_title) {
    [#kind #callout_num]
  } else {
    [#kind #callout_num: #old_title]
  }

  let new_title_block = block_with_new_content(
    old_title_block,
    block_with_new_content(
      old_title_block.body,
      if children.len() == 1 {
        new_title  // no icon: just the title
      } else {
        children.at(0) + new_title  // with icon: preserve icon block + new title
      }))

  align(left, block_with_new_content(old_callout,
    block(below: 0pt, new_title_block) +
    old_callout.body.children.at(1)))
}

// 2023-10-09: #fa-icon("fa-info") is not working, so we'll eval "#fa-info()" instead
#let callout(body: [], title: "Callout", background_color: rgb("#dddddd"), icon: none, icon_color: black, body_background_color: white) = {
  block(
    breakable: false, 
    fill: background_color, 
    stroke: (paint: icon_color, thickness: 0.5pt, cap: "round"), 
    width: 100%, 
    radius: 2pt,
    block(
      inset: 1pt,
      width: 100%, 
      below: 0pt, 
      block(
        fill: background_color,
        width: 100%,
        inset: 8pt)[#if icon != none [#text(icon_color, weight: 900)[#icon] ]#title]) +
      if(body != []){
        block(
          inset: 1pt, 
          width: 100%, 
          block(fill: body_background_color, width: 100%, inset: 8pt, body))
      }
    )
}



// Póster académico UNAL, Primera Entrega (Fase 1).
// Lienzo 120 x 90 cm horizontal. Jerarquía tipográfica de la plantilla:
// título 66 pt, secciones 50 pt, texto 32 pt, referencias y pies 24 pt.
// Tipografía institucional: Ancízar Sans (texto) y Ancízar Serif (referencias).

#let verde-osc = rgb("#456A3E")
#let verde = rgb("#94B43B")
#let gris = rgb("#55595B")
#let fondo = rgb("#F3F4F1")

#let ancho-col = 37.6cm
#let alto-fila = 27.4cm

// Tarjeta de sección numerada.
#let seccion(num, titulo, subtitulo: none, cuerpo) = block(
  width: 100%, height: alto-fila, fill: white, inset: (x: 1.3cm, top: 1.0cm, bottom: 0.8cm),
  stroke: (top: 8pt + verde),
)[
  #text(size: 50pt, weight: "bold", fill: verde-osc)[#num. #titulo]
  #if subtitulo != none { h(0.4em); text(size: 32pt, fill: gris)[(#subtitulo)] }
  #v(0.5cm)
  #cuerpo
]

// Figura con pie de texto a 24 pt.
#let figura(ruta, pie, ancho: 100%) = block(width: 100%, breakable: false)[
  #align(center, image(ruta, width: ancho))
  #v(0.15cm)
  #text(size: 24pt, fill: gris)[#pie]
]

// Cifra destacada.
#let cifra(valor, etiqueta) = box(width: 100%, inset: (y: 0.3cm))[
  #text(size: 60pt, weight: "bold", fill: verde-osc)[#valor] \
  #text(size: 24pt, fill: gris)[#etiqueta]
]

// Recuadro de énfasis.
#let destacado(cuerpo) = block(width: 100%, fill: verde.lighten(80%), inset: 0.8cm, stroke: (left: 10pt + verde))[#cuerpo]

#let poster-unal(
  titulo: none, subtitulo: none, estudiante: none, programa: none, facultad: none, grupo: none,
  logo-izq: none, body,
) = {
  set page(width: 120cm, height: 90cm, margin: 2cm, fill: fondo, numbering: none, header: none, footer: none)
  set text(font: ("Ancizar Sans", "Helvetica Neue"), size: 32pt, fill: rgb("#222222"), lang: "es")
  set par(justify: false, leading: 0.55em, spacing: 0.75em)
  set list(indent: 0.4em, body-indent: 0.5em, spacing: 0.6em, marker: text(fill: verde)[■])
  set enum(indent: 0.4em, body-indent: 0.5em, spacing: 0.6em)
  show strong: set text(fill: verde-osc)

  // Encabezado: logo | título | datos del estudiante.
  grid(
    columns: (12cm, 1fr, 27cm), column-gutter: 1.5cm, align: (center + horizon, center + horizon, left + horizon),
    if logo-izq != none { image(logo-izq, height: 11.5cm) },
    [
      #text(size: 66pt, weight: "bold", fill: verde-osc, hyphenate: false)[#titulo]
      #if subtitulo != none { v(0.3cm); text(size: 36pt, style: "italic", fill: gris)[#subtitulo] }
    ],
    [
      #text(size: 40pt, weight: "bold", fill: verde-osc)[#estudiante] \
      #v(0.2cm)
      #text(size: 30pt)[#programa] \
      #text(size: 28pt, fill: gris)[#facultad] \
      #text(size: 28pt, fill: gris)[#grupo]
    ],
  )
  v(0.4cm)
  line(length: 100%, stroke: 6pt + verde)
  v(0.5cm)
  body
}
#let brand-color = (:)
#let brand-color-background = (:)
#let brand-logo = (:)

#set page(
  paper: "us-letter",
  margin: (x: 1.25in, y: 1.25in),
  numbering: "1",
  columns: 1,
)

#show: doc => poster-unal(
   titulo: [Modelación analítica de la heterogeneidad espacial y minería de texto sobre el feminicidio en el departamento de Antioquia para el diseño de políticas públicas de prevención territorial], 
   subtitulo: [\(Formato Primera Entrega Póster)], 
   estudiante: [Daniel Felipe Villa Rengifo], 
   programa: [Maestría en Ingeniería -- Analítica], 
   facultad: [Facultad de Minas · Universidad Nacional de Colombia, Sede Medellín], 
   grupo: [Departamento de Ciencias de la Computación y la Decisión], 
   logo-izq: "logos/escudo-unal-2016.svg", 
  doc,
)


#grid(
  columns: (1fr, 1fr, 1fr), column-gutter: 1.2cm, row-gutter: 1.0cm,

  seccion(1, [Motivación], subtitulo: [Contexto / Propósito])[
    #figura("figuras/f1_tasas.svg")[*Figura 1.* Homicidios de mujeres por cada 100.000 mujeres. Fuente: Medicina Legal y proyecciones DANE. \*2025 preliminar.]
    #v(0.3cm)
    - En 2023 fueron asesinadas *124* mujeres en Antioquia (Medicina Legal; 126 según la Policía).
    - La tasa bajó de 5,4 a 3,1 entre 2018 y 2024; desde 2022 está por debajo de la nacional.
    - *48 %* de los casos ocurre en zona rural.
    #destacado[*Propósito:* integrar registros oficiales y textos públicos para explicar por qué el riesgo cambia de un municipio a otro.]
  ],

  seccion(2, [Marco teórico], subtitulo: [De referencia])[
    - *Continuum de violencia:* el feminicidio es el desenlace de violencias previas, no un hecho aislado.
    - *Heterogeneidad espacial:* los factores asociados no pesan igual en todo el territorio; la regresión de Poisson geográficamente ponderada los estima por zona (Nakaya et al., 2005).
    - *Marco legal:* Ley 1257 de 2008 y Ley 1761 de 2015, que tipifica el feminicidio como delito autónomo.
    - *Minería de texto:* permite recuperar arma, vínculo y lugar a partir de relatos de prensa (García Alzate, 2022).
    #v(0.2cm)
    #figura("figuras/f2_tipificacion.svg")[*Figura 2.* Víctimas registradas por feminicidio en Colombia. La tipificación crece después de la Ley 1761 de 2015. Fuente: Fiscalía General de la Nación.]
  ],

  seccion(3, [Qué], subtitulo: [Objeto de estudio])[
    - *Objeto:* la violencia letal contra las mujeres en los 125 municipios de Antioquia.
    - *Sistema:* casos y tasas por municipio y año (2015–2026).
    - *Entorno:* ruralidad, conflicto armado, economías ilegales y discurso público en prensa y redes.
    - *Unidad de análisis:* municipio–año.
    #v(0.2cm)
    #figura("figuras/f3_municipios.svg")[*Figura 3.* Municipios con más homicidios de mujeres, 2018–2026. Medellín concentra 22 %; el Bajo Cauca aparece con cuatro municipios. Fuente: Policía Nacional.]
  ],

  seccion(4, [Proceso o método], subtitulo: [Cómo])[
    #let paso(n, t, d) = block(width: 100%, height: 8.8cm, fill: verde.lighten(82%), inset: 0.5cm, radius: 0.3cm)[
      #text(size: 26pt, weight: "bold", fill: verde-osc)[#n. #t] \
      #text(size: 22pt)[#d]
    ]
    #let flecha = text(size: 40pt, fill: verde)[→]
    #grid(columns: (1fr, auto, 1fr, auto, 1fr, auto, 1fr), column-gutter: 0.25cm, align: horizon,
      paso(1, [Adquisición], [APIs de datos.gov.co, 88 boletines, 113 noticias, 102 posts en X y 16 comentarios en Facebook]), flecha,
      paso(2, [Validación], [Fiabilidad A–F y credibilidad 1–6; contraste entre registros]), flecha,
      paso(3, [Exploración], [Tasas con población DANE, comparación departamental y municipal]), flecha,
      paso(4, [Fase 2], [Modelo espacial con variables de texto]),
    )
    #v(0.4cm)
    #text(size: 34pt, weight: "bold", fill: verde-osc)[Alcance según los datos]
    #v(0.1cm)
    #set text(size: 26pt)
    #table(columns: (8cm, 1fr), stroke: none, inset: (x: 0.3cm, y: 0.28cm), fill: (_, y) => if calc.odd(y) { verde.lighten(85%) },
      [*Descriptivo*], [Alcanzado: tasas, comparaciones y concentración territorial.],
      [*Reactivo*], [Posible: prensa y redes se actualizan a diario.],
      [*Explicativo*], [Objetivo de la tesis: panel municipal 2015–2025.],
      [*Anticipativo*], [No viable: pocos casos por municipio y rezago en la tipificación.],
    )
    #v(0.2cm)
    *Limitaciones:* subregistro; cifras 2025–2026 preliminares; 26 boletines escaneados sin texto; Facebook sin sesión solo muestra publicaciones recientes.
  ],

  seccion(5, [Avances RSL])[
    - *Protocolo:* Kitchenham y PRISMA 2020.
    - *Corpus preliminar:* 87 fuentes y 8 conjuntos de datos, cada uno con su nivel de fiabilidad.
    #v(0.1cm)
    #figura("figuras/f4_fuentes.svg")[*Figura 4.* Fuentes consultadas por tipo y fiabilidad de la fuente (escala A–F del código Admiralty).]
    #v(0.2cm)
    - *Hallazgo:* el trabajo de referencia extrae casos de una sola fuente no oficial y no incorpora el territorio (García Alzate, 2022).
    - *Brecha:* en el corpus revisado no hay modelos municipales para Antioquia que combinen registros oficiales, texto y espacio.
  ],

  seccion(6, [Identificación del problema])[
    Policía y Medicina Legal coinciden en el número de víctimas (≤ 10 % de diferencia en 10 de 12 años), pero no explican por qué:
    - En 56 % a 79 % de los casos no se sabe quién fue el agresor.
    - Solo 55 % (2023) y 70 % (2024) de los homicidios de mujeres quedan registrados como feminicidio.
    #v(0.1cm)
    #figura("figuras/f5_brecha.svg")[*Figura 5.* Antioquia: tres formas de contar. Fuentes: Medicina Legal, Observatorio Feminicidios Colombia y Fiscalía.]
    #destacado[*Pregunta:* ¿qué factores territoriales y discursivos explican la variación municipal de la violencia letal contra las mujeres en Antioquia?]
  ],
)

#v(1.0cm)

#grid(
  columns: (1fr, 1fr, 1fr), column-gutter: 1.2cm,
  block(width: 100%, height: 13.6cm, fill: white, inset: (x: 1.3cm, y: 0.9cm), stroke: (top: 8pt + verde))[
    #text(size: 44pt, weight: "bold", fill: verde-osc)[7\. Referencias]
    #v(0.2cm)
    #set text(font: "Ancizar Serif", size: 22pt)
    #set par(hanging-indent: 1.2em, leading: 0.45em, spacing: 0.5em)
    Congreso de la República de Colombia. (2015). _Ley 1761 de 2015, por la cual se crea el tipo penal de feminicidio como delito autónomo_. Diario Oficial.

    Fiscalía General de la Nación. (2026). _Víctimas Fiscalía – V3_ [Conjunto de datos]. Datos Abiertos Colombia. https://www.datos.gov.co/d/hr73-zqjf

    García Alzate, D. (2022). _Seguimiento de casos de feminicidio en Colombia mediante técnicas de minería de texto_ [Tesis de maestría, Universidad Nacional de Colombia].

    Instituto Nacional de Medicina Legal y Ciencias Forenses. (2025). _Presuntos homicidios. Colombia, 2015 a 2024. Cifras definitivas_ [Conjunto de datos]. https://www.datos.gov.co/d/vtub-3de2

    Nakaya, T., Fotheringham, A. S., Brunsdon, C. y Charlton, M. (2005). Geographically weighted Poisson regression for disease association mapping. _Statistics in Medicine, 24_(17), 2695–2717.

    Observatorio Feminicidios Colombia. (2017–2024). _Ni una menos: boletín de feminicidios en Medellín y el Valle de Aburrá_. Red Feminista Antimilitarista.
  ],
  block(width: 100%, height: 13.6cm, fill: white, inset: (x: 1.3cm, y: 0.9cm), stroke: (top: 8pt + verde))[
    #text(size: 44pt, weight: "bold", fill: verde-osc)[Más información]
    #v(0.3cm)
    #grid(columns: (9.5cm, 1fr), column-gutter: 1cm, align: horizon,
      image("figuras/qr_repositorio.svg", width: 9.5cm),
      [
        #text(size: 28pt)[Repositorio del proyecto: código, datos procesados y notas de trabajo.]
        #v(0.4cm)
        #text(size: 22pt, fill: gris)[github.com/dvillaunal/Msc-Project]
      ],
    )
  ],
  block(width: 100%, height: 13.6cm, fill: white, inset: (x: 1.3cm, y: 0.9cm), stroke: (top: 8pt + verde))[
    #text(size: 44pt, weight: "bold", fill: verde-osc)[Directores / Asesores]
    #v(0.5cm)
    #grid(columns: (1fr, 9.5cm), column-gutter: 1cm, align: horizon,
      [
        #text(size: 36pt, weight: "bold")[Fernán Alonso Villa Garzón, Ph.D.] \
        #text(size: 28pt, fill: gris)[Tutor] \
        #v(0.3cm)
        #text(size: 26pt, fill: gris)[Departamento de Ciencias de la Computación y la Decisión, Facultad de Minas]
      ],
      image("logos/logotipo-unal.svg", width: 9.5cm),
    )
  ],
)



