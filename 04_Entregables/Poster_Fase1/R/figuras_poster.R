# Figuras del póster: SVG vectoriales al tamaño físico en que se imprimen (texto ≥ 24 pt).

suppressPackageStartupMessages({ library(ggplot2); library(svglite); library(forcats) })

VERDE_OSC <- "#456A3E"; VERDE <- "#94B43B"; GRIS <- "#55595B"; GRIS_CLARO <- "#BFC3BC"
FUENTE <- "Ancizar Sans"
dir.create("figuras", showWarnings = FALSE)

tema <- function(base = 26) {
  theme_minimal(base_size = base, base_family = FUENTE) +
    theme(panel.grid.minor = element_blank(), panel.grid.major.x = element_blank(),
          panel.grid.major.y = element_line(colour = "#E3E5E0", linewidth = 0.6),
          axis.text = element_text(colour = GRIS), axis.title = element_text(colour = GRIS, size = base - 2),
          legend.position = "top", legend.justification = "left", legend.title = element_blank(),
          legend.text = element_text(size = base - 2), plot.margin = margin(6, 14, 6, 6))
}
guardar <- function(g, nombre, ancho_cm, alto_cm) {
  ruta <- file.path("figuras", paste0(nombre, ".svg"))
  svglite(ruta, width = ancho_cm / 2.54, height = alto_cm / 2.54, system_fonts = list(sans = FUENTE))
  print(g); invisible(dev.off()); ruta
}
pt <- function(x) x / .pt  # tamaño de geom_text en puntos

# 1. Tasa de homicidio de mujeres: Antioquia y Colombia
fig_tasas <- function() {
  firme <- filter(tasas, !preliminar | anio == 2024)
  prelim <- filter(tasas, anio >= 2024)
  # rótulo arriba para la serie más alta de cada año y abajo para la más baja
  rotulos <- filter(tasas, anio %in% c(2018, 2024)) |> group_by(anio) |>
    mutate(vj = ifelse(tasa == max(tasa), -0.9, 1.9)) |> ungroup()
  ggplot(tasas, aes(anio, tasa, colour = serie)) +
    geom_line(data = firme, linewidth = 2.2) +
    geom_line(data = prelim, linewidth = 2.2, linetype = "22") +
    geom_point(size = 5) +
    geom_text(data = rotulos, aes(label = num(tasa, 1), vjust = vj),
              size = pt(24), show.legend = FALSE, family = FUENTE) +
    scale_colour_manual(values = c(Antioquia = VERDE_OSC, Colombia = GRIS_CLARO)) +
    scale_x_continuous(breaks = 2018:2025, labels = c(2018:2024, "2025*")) +
    scale_y_continuous(limits = c(0, 7), breaks = seq(0, 6, 2)) +
    labs(x = NULL, y = NULL) + tema()
}

# 2. Víctimas registradas por feminicidio en Colombia (Fiscalía)
fig_tipificacion <- function() {
  d <- nacional(fis) |> filter(anio >= 2015, anio <= 2024)
  ggplot(d, aes(anio, n)) +
    geom_col(fill = VERDE, width = 0.7) +
    geom_text(aes(label = num(n)), vjust = -0.4, size = pt(22), colour = GRIS, family = FUENTE) +
    scale_x_continuous(breaks = 2015:2024) +
    scale_y_continuous(expand = expansion(mult = c(0, 0.18))) +
    labs(x = NULL, y = NULL) + tema(24) + theme(axis.text.y = element_blank(), panel.grid.major.y = element_blank())
}

# 3. Municipios con más homicidios de mujeres (Policía, 2018 a hoy), por subregión
SUBREGION <- c(MEDELLIN = "Valle de Aburrá", BELLO = "Valle de Aburrá", ITAGUI = "Valle de Aburrá",
               CAUCASIA = "Bajo Cauca", CACERES = "Bajo Cauca", TARAZA = "Bajo Cauca", `EL BAGRE` = "Bajo Cauca",
               TURBO = "Urabá", APARTADO = "Urabá", `CIUDAD BOLIVAR` = "Suroeste", REMEDIOS = "Nordeste")
NOMBRE <- c(MEDELLIN = "Medellín", BELLO = "Bello", ITAGUI = "Itagüí", CAUCASIA = "Caucasia", CACERES = "Cáceres",
            TARAZA = "Tarazá", `EL BAGRE` = "El Bagre", TURBO = "Turbo", APARTADO = "Apartadó",
            `CIUDAD BOLIVAR` = "Ciudad Bolívar", REMEDIOS = "Remedios")
fig_municipios <- function(k = 10) {
  d <- muni |> slice_max(n, n = k, with_ties = FALSE) |>
    mutate(sub = coalesce(SUBREGION[municipio], "Otra"), nom = coalesce(NOMBRE[municipio], str_to_title(municipio)),
           nom = fct_reorder(nom, n), sub = factor(sub, levels = c("Valle de Aburrá", "Bajo Cauca", "Urabá", "Suroeste", "Nordeste", "Otra")))
  ggplot(d, aes(n, nom, fill = sub)) +
    geom_col(width = 0.72) +
    geom_text(aes(label = paste0(num(n), "  (", pct(p), ")")), hjust = -0.08, size = pt(22), colour = GRIS, family = FUENTE) +
    scale_fill_manual(values = c(`Valle de Aburrá` = VERDE_OSC, `Bajo Cauca` = VERDE, `Urabá` = "#C9D99A",
                                 Suroeste = GRIS_CLARO, Nordeste = "#8E938B", Otra = "#DDDDDD"), drop = TRUE) +
    scale_x_continuous(expand = expansion(mult = c(0, 0.32))) +
    labs(x = NULL, y = NULL) + tema(24) +
    theme(axis.text.x = element_blank(), panel.grid.major.y = element_blank(), legend.text = element_text(size = 22))
}

# 4. Fuentes del corpus preliminar por tipo y fiabilidad
fig_fuentes <- function() {
  d <- fuentes |> count(tipo, letra) |> group_by(tipo) |> mutate(total = sum(n)) |> ungroup() |>
    mutate(tipo = fct_reorder(tipo, total), letra = factor(letra, levels = c("A", "B", "C", "D", "E", "F")))
  tot <- distinct(d, tipo, total)
  ggplot(d, aes(n, tipo, fill = letra)) +
    geom_col(width = 0.7) +
    geom_text(data = tot, aes(total, tipo, label = total), inherit.aes = FALSE, hjust = -0.3, size = pt(22), colour = GRIS, family = FUENTE) +
    scale_fill_manual(values = c(A = "#2E4A2A", B = VERDE_OSC, C = VERDE, D = "#C9D99A", E = GRIS_CLARO, F = "#E6E7E3"),
                      labels = c(A = "A fiable", B = "B generalmente fiable", C = "C bastante fiable", D = "D no siempre fiable",
                                 E = "E poco segura", F = "F sin evaluar"), drop = TRUE) +
    scale_x_continuous(expand = expansion(mult = c(0, 0.12))) +
    labs(x = NULL, y = NULL) + tema(22) +
    theme(axis.text.x = element_blank(), panel.grid.major.y = element_blank(), legend.text = element_text(size = 20)) +
    guides(fill = guide_legend(nrow = 2))
}

# 5. Antioquia: homicidios de mujeres, feminicidios tipificados y registro del Observatorio
fig_brecha <- function() {
  d <- tip |> filter(anio >= 2018, anio <= 2024) |> left_join(obs, by = "anio") |>
    pivot_longer(c(ml, fis, obs), names_to = "fuente", values_to = "n") |> filter(!is.na(n)) |>
    mutate(fuente = factor(fuente, levels = c("ml", "obs", "fis"),
                           labels = c("Homicidios de mujeres (Medicina Legal)", "Feminicidios (Observatorio)", "Tipificados (Fiscalía)")))
  ggplot(d, aes(factor(anio), n, fill = fuente)) +
    geom_col(position = position_dodge2(preserve = "single", padding = 0.12), width = 0.82) +
    geom_text(aes(label = n), position = position_dodge2(width = 0.82, preserve = "single"), vjust = -0.35,
              size = pt(19), colour = GRIS, family = FUENTE) +
    scale_fill_manual(values = c(VERDE_OSC, VERDE, GRIS_CLARO)) +
    scale_y_continuous(expand = expansion(mult = c(0, 0.38))) +
    labs(x = NULL, y = NULL) + tema(22) +
    theme(axis.text.y = element_blank(), panel.grid.major.y = element_blank(), legend.text = element_text(size = 20)) +
    guides(fill = guide_legend(nrow = 1))
}

# QR al repositorio del proyecto
qr_repo <- function(url) {
  qrcode::generate_svg(qrcode::qr_code(url, ecl = "M"), filename = "figuras/qr_repositorio.svg",
                       size = 600, foreground = VERDE_OSC, background = "white", show = FALSE)
  "figuras/qr_repositorio.svg"
}
