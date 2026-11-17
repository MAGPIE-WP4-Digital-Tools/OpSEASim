class Cargo:
    def __init__(self, code, name, specificHeat, lowerBound, upperBound, resp_f = None, resp_g = None,  density = None):
        self._code           = code          # Integer
        self._name           = name          # String
        self._specificHeat   = specificHeat  # Float, in J/(Kg*K)    
        self._lowerBound     = lowerBound    # Float, in °C
        self._upperBound     = upperBound    # Float, in °C
        self._resp_f         = resp_f        # Float, dimensionless
        self._resp_g         = resp_g        # Float, dimensionless
        self._density        = density       # Float, in TO DO

    @property
    def code(self):
        return self._code

    @property
    def name(self):
        return self._name

    @property
    def specificHeat(self):
        return self._specificHeat
    
    @property
    def lowerBound(self):
        return self._lowerBound
    
    @property
    def upperBound(self):
        return self._upperBound
    
    @property
    def resp_f(self):
        return self._resp_f
    
    @property
    def resp_g(self):
        return self._resp_g
    
    @property
    def density(self):
        return self._density
    
