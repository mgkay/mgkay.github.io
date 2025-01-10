# Road Network Functions

using DataFrames
using CairoMakie, Logjam.MapTools
using DelaunayTriangulation

function prune_reindex(df_links::DataFrame, df_nodes::DataFrame)
    # Find vertices common to df_links and df_nodes
    vtx = intersect(union(df_links[:, 1], df_links[:, 2]), df_nodes[:, 1])

    # Prune rows in df_links and df_nodes based on common vertices
    df_links_out = filter(row -> (row[1] in vtx) && (row[2] in vtx), df_links)
    df_nodes_out = filter(row -> row[1] in vtx, df_nodes)

    # Create mapping and reindex src (col 1) and dst (col 2)
    vtx_map = Dict(v => i for (i, v) in enumerate(vtx))
    for row in eachrow(df_links_out)
        row[1] = vtx_map[row[1]]
        row[2] = vtx_map[row[2]]
    end

    # Reindex idx (col 1)
    df_nodes_out[:, 1] .= [vtx_map[row[1]] for row in eachrow(df_nodes_out)]
    sort!(df_nodes_out, 1)
    
    return df_links_out, df_nodes_out
end

x2ln(g, x) = vcat(map(e -> [x[src(e)], x[dst(e)], NaN], edges(g))...)

function dgc(xy₁, xy₂; unit=:mi)
    length(xy₁) == length(xy₂) == 2 || error("Inputs must have length 2.")
    unit in [:mi, :km] || error("Unit must be :mi or :km")

    Δx, Δy = xy₂[1] - xy₁[1], xy₂[2] - xy₁[2]
    a = sind(Δy / 2)^2 + cosd(xy₁[2]) * cosd(xy₂[2]) * sind(Δx / 2)^2
    2 * asin(min(sqrt(a), 1.0)) * (unit == :mi ? 3958.75 : 6371.00)
end
Dgc(X₁, X₂) = [dgc(i, j) for i in eachrow(X₁), j in eachrow(X₂)]

function addconnectors(dfL, dfN, x′, y′)
    g = 1.3   # Interior circuity factor
    n = length(x′)
    b, e, d = dfL[:, 1], dfL[:, 2], dfL[:, 3]
    idx, x, y = dfN[:, 1], dfN[:, 2], dfN[:, 3]
    tri = triangulate(collect(zip(x, y)))
    b′, e′, d′ = Int[], Int[], Float64[]
    for i = 1:n
        t = brute_force_search(tri, (x′[i], y′[i]))
        t = filter(x -> x > 0, t)
        dᵢ = [g*dgc((x′[i], y′[i]), (x[j], y[j])) for j in t]
        for (j,k) in enumerate(t)
            push!(b′, i)
            push!(e′, k + n)
            push!(d′, dᵢ[j]) 
        end
    end
    b .+= n
    append!(b, b′)
    e .+= n
    append!(e, e′)
    append!(d, d′)
    idx .+= n
    prepend!(idx, 1:n)
    prepend!(x, x′)
    prepend!(y, y′)
    dfLout = DataFrame(Symbol(names(dfL)[1]) => b, Symbol(names(dfL)[2]) => e, 
        Symbol(names(dfL)[3]) => d)
    dfNout = DataFrame(Symbol(names(dfN)[1]) => idx, Symbol(names(dfN)[2]) => x, 
        Symbol(names(dfN)[3]) => y)
    return dfLout, dfNout
end
