// src/components/framerate-viewer/FrameRateViewer.tsx
import {useState} from "react"
import clsx from "clsx"
import FramerateTimeseriesView from "./FramerateTimeseriesView"
import FramerateHistogramView from "./FramerateHistogramView"
import FramerateStatisticsView from "./FramerateStatisticsView"
import { useTranslation } from "react-i18next"

export const frontendColor: string = "var(--chart-frontend)"
export const backendColor: string = "var(--chart-backend)"

export const FramerateViewerPanel = () => {
    const { t } = useTranslation()
    const [showStats, setShowStats] = useState(true)
    const [showTimeseries, setShowTimeseries] = useState(true)
    const [showHistogram, setShowHistogram] = useState(true)

    return (
        <div className="framerate-viewer">
            {/* Header */}
            <div className="framerate-viewer-header">
                <p className="text bg text-gray">{t('cameraPerformanceMetrics')}</p>
                <div className="flex gap-1">
                    <button
                        className={clsx("button sm br-1", showStats && "activated")}
                        onClick={() => setShowStats(v => !v)}
                        title={t("statisticsView")}
                    >
                        <p className="text sm">Stats</p>
                    </button>
                    <button
                        className={clsx("button sm br-1", showTimeseries && "activated")}
                        onClick={() => setShowTimeseries(v => !v)}
                        title={t("timelineView")}
                    >
                        <p className="text sm">Timeline</p>
                    </button>
                    <button
                        className={clsx("button sm br-1", showHistogram && "activated")}
                        onClick={() => setShowHistogram(v => !v)}
                        title={t("distributionView")}
                    >
                        <p className="text sm">Dist.</p>
                    </button>
                </div>
            </div>

            {/* Stats table */}
            {showStats && (
                <div className="framerate-stats-wrapper br-1 border-1 border-black p-1">
                    <FramerateStatisticsView compact={true} />
                </div>
            )}

            {/* Chart area */}
            <div className={clsx("framerate-charts-area", showTimeseries && showHistogram ? "row" : "column")}>
                {showTimeseries && (
                    <div className="framerate-chart-panel border-1 border-black br-1">
                        <FramerateTimeseriesView
                            frontendColor={frontendColor}
                            backendColor={backendColor}
                            title={t("framerateTimeline")}
                        />
                    </div>
                )}
                {showHistogram && (
                    <div className="framerate-chart-panel border-1 border-black br-1">
                        <FramerateHistogramView
                            frontendColor={frontendColor}
                            backendColor={backendColor}
                            title={t("framerateDistribution")}
                        />
                    </div>
                )}
            </div>
        </div>
    )
}

export default FramerateViewerPanel
