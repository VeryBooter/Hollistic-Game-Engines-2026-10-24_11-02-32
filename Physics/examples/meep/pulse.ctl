; Real Meep Scheme input, UNVERIFIED until Meep is built.
; Meep is dimensionless: this example's length unit is 1 micrometre.
; physical time = Meep time * length_unit_m / c0.
(set! geometry-lattice (make lattice (size no-size no-size 10)))
(set! resolution 20)
(set! pml-layers (list (make pml (thickness 1))))
(set! sources (list (make source
  (src (make gaussian-src (frequency 1) (fwidth 0.5)))
  (component Ex) (center 0 0 0))))
(run-until 20 (at-end output-efield-x))
