from qgis.core import (QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField, QgsProcessingParameterString, QgsProcessingParameterNumber,
    QgsProcessingParameterVectorDestination, QgsProcessingException, QgsField, QgsFeature, QgsProcessing)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QIcon

class AlgSVI(QgsProcessingAlgorithm):
    INPUT="INPUT"; NEG_FIELDS="NEG_FIELDS"; POS_FIELDS="POS_FIELDS"
    W_NEG="W_NEG"; W_POS="W_POS"; PREFIX="PREFIX"; OUTPUT="OUTPUT"
    def name(self): return "svi_index"
    def displayName(self): return "Social Vulnerability Index (SVI)"
    def group(self): return "Social Analysis"
    def groupId(self): return "social_analysis"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT,"Input polygons",
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(self.NEG_FIELDS,"Negative indicators (higher=worse)",
            parentLayerParameterName=self.INPUT, type=QgsProcessingParameterField.Numeric, allowMultiple=True))
        self.addParameter(QgsProcessingParameterField(self.POS_FIELDS,"Positive indicators (higher=better)",
            parentLayerParameterName=self.INPUT, type=QgsProcessingParameterField.Numeric, allowMultiple=True, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.W_NEG,"Weight negative",
            type=QgsProcessingParameterNumber.Double, defaultValue=0.6, minValue=0.0, maxValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(self.W_POS,"Weight positive",
            type=QgsProcessingParameterNumber.Double, defaultValue=0.4, minValue=0.0, maxValue=1.0))
        self.addParameter(QgsProcessingParameterString(self.PREFIX,"Output prefix", defaultValue="svi_"))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT,"Output"))

    def processAlgorithm(self, p, context, feedback):
        src = self.parameterAsSource(p, self.INPUT, context)
        neg = self.parameterAsFields(p, self.NEG_FIELDS, context) or []
        pos = self.parameterAsFields(p, self.POS_FIELDS, context) or []
        wN  = self.parameterAsDouble(p, self.W_NEG, context)
        wP  = self.parameterAsDouble(p, self.W_POS, context)
        pref= self.parameterAsString(p, self.PREFIX, context)
        if src is None or (not neg and not pos): raise QgsProcessingException("Add at least one indicator.")
        if abs((wN+wP)-1.0) > 1e-6: raise QgsProcessingException("Weights must sum to 1.0.")

        flds = src.fields(); score_name = f"{pref}score"
        if flds.indexOf(score_name) == -1: flds.append(QgsField(score_name, QVariant.Double))
        (sink, dest) = self.parameterAsSink(p, self.OUTPUT, context, flds, src.wkbType(), src.sourceCrs())

        feats = list(src.getFeatures())
        def tofloat(v):
            try:
                return float(v) if v is not None else None
            except (ValueError, TypeError):
                return None
        def norm(col):
            vals=[tofloat(v) for v in col]; clean=[v for v in vals if v is not None]
            if not clean: return [None]*len(vals)
            lo, hi = min(clean), max(clean)
            return [0.0 if v is not None and hi==lo else (None if v is None else (v-lo)/(hi-lo)) for v in vals]

        neg_cols = {f: [tofloat(ft[f]) for ft in feats] for f in neg}
        pos_cols = {f: [tofloat(ft[f]) for ft in feats] for f in pos}
        neg_norm = {f: norm(neg_cols[f]) for f in neg}
        pos_norm = {f: norm(pos_cols[f]) for f in pos}

        for i, ft in enumerate(feats):
            if feedback.isCanceled(): break
            nvals = [neg_norm[f][i] for f in neg if neg_norm[f][i] is not None]
            pvals = [1.0 - pos_norm[f][i] for f in pos if pos_norm[f][i] is not None]
            score = wN*(sum(nvals)/len(nvals) if nvals else 0.0) + wP*(sum(pvals)/len(pvals) if pvals else 0.0)
            out = QgsFeature(flds); out.setGeometry(ft.geometry())
            attrs = ft.attributes()
            if flds.indexOf(score_name) == len(attrs): attrs = attrs + [round(score,4)]
            else: attrs[flds.indexOf(score_name)] = round(score,4)
            out.setAttributes(attrs); sink.addFeature(out)
        return {self.OUTPUT: dest}

    def createInstance(self): return AlgSVI()

    def icon(self):
        import os
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "Social_Analysis_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))
    def shortHelpString(self): return "SVI = weighted mean of min–max normalised indicators (neg worse, pos better)."
