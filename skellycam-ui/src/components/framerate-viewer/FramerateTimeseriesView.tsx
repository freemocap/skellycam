// src/components/framerate-viewer/FramerateTimeseriesView.tsx
import { useRef, useEffect, useState } from "react"
import * as d3 from "d3"
import { Box, IconButton, Tooltip, Typography, Fade } from "@mui/material"
import { useTheme } from "@mui/material/styles"
import { ZoomIn, ZoomOut, RestartAlt } from "@mui/icons-material"

type FrameRateData = {
  timestamp: number
  value: number
}

type FrameRateSource = {
  id: string
  name: string
  color: string
  data: FrameRateData[]
}

type FrameRateTimeseriesProps = {
  sources: FrameRateSource[]
  title?: string
}

export default function FramerateTimeseriesView({
  sources,
  title = "Frame Duration Over Time"
}: FrameRateTimeseriesProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const theme = useTheme()
  const [transform, setTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity)
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const [showControls, setShowControls] = useState(false)

  useEffect(() => {
    if (!svgRef.current) return

    // Clear previous chart
    d3.select(svgRef.current).selectAll("*").remove()

    if (sources.length === 0 || sources.every((s) => s.data.length === 0)) {
      // Draw empty chart with axes
      const margin = { top: 20, right: 30, bottom: 30, left: 60 }
      const width = svgRef.current.clientWidth - margin.left - margin.right
      const height = svgRef.current.clientHeight - margin.top - margin.bottom

      const svg = d3.select(svgRef.current).append("g").attr("transform", `translate(${margin.left},${margin.top})`)

      // Create empty scales
      const xScale = d3
        .scaleTime()
        .domain([new Date(Date.now() - 10000), new Date()])
        .range([0, width])

      const yScale = d3.scaleLinear().domain([0, 100]).range([height, 0])

      // Create axes
      const xAxis = d3
        .axisBottom(xScale)
        .ticks(5)
        .tickSize(-height)
        .tickFormat(d3.timeFormat("%H:%M:%S") as any)

      const yAxis = d3.axisLeft(yScale).ticks(10).tickSize(-width)

      // Add X axis
      svg
        .append("g")
        .attr("class", "x-axis")
        .style("font-family", "monospace")
        .style("font-size", "10px")
        .style("color", theme.palette.text.secondary)
        .attr("transform", `translate(0,${height})`)
        .call(xAxis)

      // Add Y axis
      svg
        .append("g")
        .attr("class", "y-axis")
        .style("font-family", "monospace")
        .style("font-size", "10px")
        .style("color", theme.palette.text.secondary)
        .call(yAxis)

      // Style grid lines
      svg.selectAll(".tick line").attr("stroke", theme.palette.divider).attr("stroke-dasharray", "2,2")

      // Add "No data" message
      svg
        .append("text")
        .attr("x", width / 2)
        .attr("y", height / 2)
        .attr("text-anchor", "middle")
        .style("font-family", "monospace")
        .style("font-size", "14px")
        .style("fill", theme.palette.text.disabled)
        .text("No data available")

      return
    }

    // Combine all data points to determine overall domain
    const allData = sources.flatMap((s) => s.data)

    // Set up dimensions
    const margin = { top: 20, right: 100, bottom: 30, left: 60 }
    const width = svgRef.current.clientWidth - margin.left - margin.right
    const height = svgRef.current.clientHeight - margin.top - margin.bottom

    // Create SVG with a clip path for zooming
    const svg = d3.select(svgRef.current).append("g").attr("transform", `translate(${margin.left},${margin.top})`)

    // Add clip path to prevent drawing outside the chart area
    svg
      .append("defs")
      .append("clipPath")
      .attr("id", "clip-time-series")
      .append("rect")
      .attr("width", width)
      .attr("height", height)

    // Create a group for the chart content that will be clipped
    const chartArea = svg.append("g").attr("clip-path", "url(#clip-time-series)")

    // Set up scales
    const xScale = d3
      .scaleTime()
      .domain(d3.extent(allData, (d) => new Date(d.timestamp)) as [Date, Date])
      .range([0, width])

    // Calculate y domain with some padding
    // For framerate data, we typically want to start from 0
    const yMax = d3.max(allData, (d) => d.value) as number
    const yPadding = Math.max(1, yMax * 0.1)

    const yScale = d3
      .scaleLinear()
      .domain([0, yMax + yPadding])
      .range([height, 0])

    // Apply the current zoom transform
    const xScaleZoomed = transform.rescaleX(xScale)
    const yScaleZoomed = transform.rescaleY(yScale)

    // Create axes
    const xAxis = d3
      .axisBottom(xScaleZoomed)
      .ticks(5)
      .tickSize(-height)
      // .tickFormat(d3.timeFormat("%S.%L") as any)

    const yAxis = d3.axisLeft(yScaleZoomed).ticks(10).tickSize(-width)

    // Add X axis
    const xAxisGroup = svg
      .append("g")
      .attr("class", "x-axis")
      .style("font-family", "monospace")
      .style("font-size", "10px")
      .style("color", theme.palette.text.secondary)
      .attr("transform", `translate(0,${height})`)
      .call(xAxis)

    xAxisGroup
      .selectAll("text")
      .style("text-anchor", "end")
      .attr("dx", "-.8em")
      .attr("dy", ".15em")
      .attr("transform", "rotate(-45)")

    // Add Y axis
    const yAxisGroup = svg
      .append("g")
      .attr("class", "y-axis")
      .style("font-family", "monospace")
      .style("font-size", "10px")
      .style("color", theme.palette.text.secondary)
      .call(yAxis)

    // Add Y axis label
    svg
      .append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", 0 - margin.left)
      .attr("x", 0 - height / 2)
      .attr("dy", "1em")
      .style("text-anchor", "middle")
      .style("font-family", "monospace")
      .style("font-size", "14px")
      .style("fill", theme.palette.text.secondary)
      .text("Frame Duration (ms)")

    // Style grid lines
    svg.selectAll(".tick line").attr("stroke", theme.palette.divider).attr("stroke-dasharray", "2,2")

    // Create line generator
    const line = d3
      .line<FrameRateData>()
      .x((d) => xScaleZoomed(new Date(d.timestamp)))
      .y((d) => yScaleZoomed(d.value))
      .curve(d3.curveLinear)

    // Add threshold lines (e.g., 16.67ms for 60fps, 33.33ms for 30fps)
    const thresholds = [
      { value: 16.67, label: "60 FPS", color: theme.palette.success.main },
      { value: 33.33, label: "30 FPS", color: theme.palette.warning.main },
    ]

    thresholds.forEach((threshold) => {
      if (threshold.value <= yMax + yPadding) {
        // Add threshold line
        chartArea
          .append("line")
          .attr("x1", 0)
          .attr("y1", yScaleZoomed(threshold.value))
          .attr("x2", width)
          .attr("y2", yScaleZoomed(threshold.value))
          .attr("stroke", threshold.color)
          .attr("stroke-width", 1)
          .attr("stroke-dasharray", "4,4")

        // Add threshold label
        chartArea
          .append("text")
          .attr("x", width)
          .attr("y", yScaleZoomed(threshold.value) - 5)
          .attr("text-anchor", "end")
          .style("font-family", "monospace")
          .style("font-size", "10px")
          .style("fill", threshold.color)
          .text(threshold.label)
      }
    })

    // Add lines and points for each source
    sources.forEach((source) => {
      if (source.data.length === 0) return

      // Add the line path
      chartArea
        .append("path")
        .datum(source.data)
        .attr("fill", "none")
        .attr("stroke", source.color)
        .attr("stroke-width", 1.5)
        .attr("d", line)

      // Add data points as circles (only if we have a reasonable number of points)
      if (source.data.length < 200) {
        chartArea
          .selectAll(`.data-point-${source.id}`)
          .data(source.data)
          .enter()
          .append("circle")
          .attr("class", `data-point-${source.id}`)
          .attr("cx", (d) => xScaleZoomed(new Date(d.timestamp)))
          .attr("cy", (d) => yScaleZoomed(d.value))
          .attr("r", 3)
          .attr("fill", source.color)
          .attr("stroke", theme.palette.background.paper)
          .attr("stroke-width", 1)
      }
    })

    // Add legend
    const legend = svg
      .append("g")
      .attr("transform", `translate(${width + 10}, 0)`)
      .attr("font-family", "monospace")
      .attr("font-size", "10px")

    sources.forEach((source, i) => {
      const legendItem = legend.append("g").attr("transform", `translate(0, ${i * 20})`)

      legendItem.append("rect").attr("width", 12).attr("height", 12).attr("fill", source.color)

      legendItem.append("text").attr("x", 20).attr("y", 10).style("fill", theme.palette.text.primary).text(source.name)
    })

    // Add tooltip functionality
    const tooltip = d3
      .select("body")
      .append("div")
      .style("position", "absolute")
      .style("background-color", theme.palette.mode === "dark" ? "rgba(0, 0, 0, 0.85)" : "rgba(255, 255, 255, 0.9)")
      .style("border", `1px solid ${theme.palette.divider}`)
      .style("border-radius", "4px")
      .style("padding", "8px")
      .style("font-family", "monospace")
      .style("font-size", "12px")
      .style("pointer-events", "none")
      .style("opacity", 0)
      .style("z-index", 1000)
      .style("color", theme.palette.text.primary)

    // Add tooltip for all data points (if we're displaying them)
    sources.forEach((source) => {
      if (source.data.length < 200) {
        chartArea
          .selectAll(`.data-point-${source.id}`)
          .on("mouseover", function (event, d) {
            d3.select(this).attr("r", 5).attr("fill", d3.color(source.color)!.brighter(0.5).toString())

            tooltip
              .style("opacity", 1)
              .html(`
                <div style="display: grid; grid-template-columns: auto auto; gap: 4px;">
                  <span style="color: ${theme.palette.text.secondary};">SOURCE:</span>
                  <span style="color: ${source.color};">${source.name}</span>
                  <span style="color: ${theme.palette.text.secondary};">TIME:</span>
                  <span>${new Date(d.timestamp).toISOString().substr(11, 12)}</span>
                  <span style="color: ${theme.palette.text.secondary};">DURATION:</span>
                  <span>${d.value.toFixed(2)} ms</span>
                  <span style="color: ${theme.palette.text.secondary};">FPS:</span>
                  <span>${(1000 / d.value).toFixed(2)}</span>
                </div>
              `)
              .style("left", event.pageX + 10 + "px")
              .style("top", event.pageY - 28 + "px")
          })
          .on("mouseout", function () {
            d3.select(this).attr("r", 3).attr("fill", source.color)

            tooltip.style("opacity", 0)
          })
      }
    })

    // Define zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 20])
      .extent([
        [0, 0],
        [width, height],
      ])
      .on("zoom", (event) => {
        // Update the transform state
        setTransform(event.transform)

        // Update axes with the new scales
        xAxisGroup.call(xAxis.scale(event.transform.rescaleX(xScale)))
        yAxisGroup.call(yAxis.scale(event.transform.rescaleY(yScale)))

        // Update all elements that depend on scales
        sources.forEach((source) => {
          if (source.data.length === 0) return

          // Update line
          chartArea
            .selectAll(`path`)
            .filter(function () {
              return d3.select(this).datum() === source.data
            })
            .attr(
              "d",
              d3
                .line<FrameRateData>()
                .x((d) => event.transform.applyX(xScale(new Date(d.timestamp))))
                .y((d) => event.transform.applyY(yScale(d.value)))
                .curve(d3.curveLinear),
            )

          // Update data points if they exist
          if (source.data.length < 200) {
            chartArea
              .selectAll(`.data-point-${source.id}`)
              .attr("cx", (d) => event.transform.applyX(xScale(new Date((d as FrameRateData).timestamp))))
              .attr("cy", (d) => event.transform.applyY(yScale((d as FrameRateData).value)))
          }
        })

        // Update threshold lines
        thresholds.forEach((threshold) => {
          if (threshold.value <= yMax + yPadding) {
            chartArea
              .selectAll("line")
              .filter(function () {
                return d3.select(this).attr("y1") === yScale(threshold.value).toString()
              })
              .attr("y1", event.transform.applyY(yScale(threshold.value)))
              .attr("y2", event.transform.applyY(yScale(threshold.value)))

            chartArea
              .selectAll("text")
              .filter(function () {
                return d3.select(this).text() === threshold.label
              })
              .attr("y", event.transform.applyY(yScale(threshold.value)) - 5)
          }
        })
      })

    // Store zoom reference for external controls
    zoomRef.current = zoom

    // Apply zoom to the SVG
    d3.select(svgRef.current).call(zoom)

    // Clean up tooltip on unmount
    return () => {
      tooltip.remove()
    }
  }, [sources, theme, transform])

  // Zoom control handlers
  const handleZoomIn = () => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 1.5)
    }
  }

  const handleZoomOut = () => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 0.75)
    }
  }

  const handleResetZoom = () => {
    if (svgRef.current && zoomRef.current) {
      d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.transform, d3.zoomIdentity)
    }
  }

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        bgcolor: "background.paper",
        position: "relative"
      }}
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => setShowControls(false)}
    >
      <Typography variant="subtitle2" sx={{ position: "absolute", top: 5, left: 10 }}>
        {title}
      </Typography>

      {/* Zoom controls that fade in/out on hover */}
      <Fade in={showControls}>
        <Box
          sx={{
            position: "absolute",
            top: "50%",
            left: 10,
            transform: "translateY(-50%)",
            zIndex: 10,
            bgcolor: "background.paper",
            borderRadius: 1,
            boxShadow: 1,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <Tooltip title="Zoom In" placement="right">
            <IconButton size="small" onClick={handleZoomIn}>
              <ZoomIn fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Zoom Out" placement="right">
            <IconButton size="small" onClick={handleZoomOut}>
              <ZoomOut fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Reset Zoom" placement="right">
            <IconButton size="small" onClick={handleResetZoom}>
              <RestartAlt fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Fade>

      <svg ref={svgRef} width="100%" height="100%" style={{ overflow: "visible" }} />
    </Box>
  )
}
