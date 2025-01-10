# Routing Functions

function tsp_total_distance(tour::Vector{Int}, D::AbstractMatrix)
    # Compute the total distance of the given tour based on the distance matrix D
    total_distance = 0.0
    for i in 1:(length(tour)-1)
        total_distance += D[tour[i], tour[i+1]]
    end
    return total_distance
end

function tsp_nearest_neighbor(D::AbstractMatrix, start_node::Int)
    n = size(D, 1)  # Number of nodes (assume square distance matrix)
    current_node = start_node  # Start at the given node
    tour = [current_node]  # Initialize tour with the starting node
    unvisited = setdiff(collect(1:n), [current_node])  # Unvisited nodes (all except start_node)

    # Build the tour by visiting nearest neighbors
    while !isempty(unvisited)
        # Find the nearest unvisited neighbor
        distances_to_unvisited = D[current_node, unvisited]
        nearest_idx = argmin(distances_to_unvisited)
        nearest_node = unvisited[nearest_idx]

        # Move to the nearest node
        push!(tour, nearest_node)
        current_node = nearest_node

        # Remove the visited node from the unvisited list
        deleteat!(unvisited, nearest_idx)
    end

    # Complete the tour by returning to the starting node
    push!(tour, start_node)

    return tour
end

function tsp_best_nearest_neighbor(D::AbstractMatrix)
    n = size(D, 1)  # Number of nodes
    best_tour = nothing
    best_distance = Inf

    # Try all nodes as the starting node
    for start_node in 1:n
        tour = tsp_nearest_neighbor(D, start_node)
        total_distance = tsp_total_distance(tour, D)

        # Update best tour if a shorter tour is found
        if total_distance < best_distance
            best_tour = tour
            best_distance = total_distance
        end
    end

    return best_tour, best_distance
end
