# Routing Functions

function tspspfillcur(XY::AbstractMatrix, k::Int=8)
    # Input Error Checking
    if size(XY, 2) != 2
        error("XY must be a 2-column matrix.")
    end

    # Compute the space-filling curve positions
    θ = sfcpos(XY[:,1], XY[:,2], k)  # Compute positions on space-filling curve

    # Generate indices for the original points (1 to n)
    indices = collect(1:size(XY, 1))

    # Sort θ while maintaining the original indices
    sorted_indices = sortperm(θ)

    # Rearrange the sorted indices
    loc = indices[sorted_indices]

    # Ensure that vertex 1 (original first vertex in XY) is the first in the sequence
    i1 = findfirst(x -> x == 1, loc)

    if i1 === nothing
        error("Vertex 1 not found in the location sequence.")
    end

    # Rearrange loc to start from vertex 1 and end at vertex 1
    loc = vcat(loc[i1:end], loc[1:i1-1], 1)

    return loc
end


function sfcpos(X::AbstractVector, Y::AbstractVector, k::Int=8)
    # Input Error Checking
    if length(X) != length(Y)
        error("X and Y must be the same length")
    elseif k < 1
        error("\"k\" must be a positive integer")
    end

    X = X[:]; Y = Y[:]

    # Check if points are in the unit square
    if any(X .< 0) || any(X .> 1) || any(Y .< 0) || any(Y .> 1)
        if length(X) == 1
            error("X, Y must be a point in the unit square (i.e., >= 0 and <= 1)")
        else
            # Scale points to the unit square
            maxrng = max(maximum(X) - minimum(X), maximum(Y) - minimum(Y))
            X = (X .- minimum(X)) ./ maxrng
            Y = (Y .- minimum(Y)) ./ maxrng
        end
    end

    # Call the recursive helper function
    return localsfcpos(X, Y, k)
end

# Recursive helper function to compute the position along the space-filling curve
function localsfcpos(X::AbstractVector, Y::AbstractVector, k::Int)
    if k == 0
        return 0.5 * ones(length(X))  # Base case, return 0.5 for all points
    end

    VN = [0 1; 3 2]  # Quadrant lookup matrix

    # Compute which quadrant the points belong to
    Quad = [VN[clamp(floor(Int, 2*X[i] + 1), 1, 2), clamp(floor(Int, 2*Y[i] + 1), 1, 2)] for i in 1:length(X)]

    # Recursively compute the position within each quadrant
    SubPos = localsfcpos(2 * abs.(X .- 0.5), 2 * abs.(Y .- 0.5), k - 1)

    # Adjust the positions for points in quadrants 1 and 3
    SubPos[Quad .== 1 .| Quad .== 3] .= 1 .- SubPos[Quad .== 1 .| Quad .== 3]

    # Compute final theta values
    theta = (Quad .+ SubPos .- 0.5) ./ 4
    return theta .- floor.(theta)  # Ensure theta is in [0, 1)
end
