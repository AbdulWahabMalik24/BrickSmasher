const page = document.body ? document.body.dataset.page : "";

async function requestJson(url, options = {}) {
    const config = { ...options, headers: { ...(options.headers || {}) } };

    if (config.body && !(config.body instanceof FormData)) {
        config.headers["Content-Type"] = "application/json";
        config.body = JSON.stringify(config.body);
    }

    const response = await fetch(url, config);
    let payload = null;

    try {
        payload = await response.json();
    } catch (error) {
        payload = null;
    }

    if (!response.ok) {
        throw new Error(payload && payload.error ? payload.error : "Request failed.");
    }

    return payload;
}

function setMessage(element, text = "", kind = "") {
    if (!element) {
        return;
    }

    element.textContent = text;
    element.className = "message";

    if (text) {
        element.classList.add("active");
    }
    if (kind) {
        element.classList.add(kind);
    }
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function initAccountPage() {
    const form = document.querySelector("#account-form");
    const message = document.querySelector("#account-message");
    if (!form || !message) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        setMessage(message, "");

        const payload = {
            firstName: form.firstName.value,
            lastName: form.lastName.value,
            email: form.email.value
        };

        try {
            const user = await requestJson("/dbUser/", {
                method: "POST",
                body: payload
            });
            form.reset();
            setMessage(
                message,
                `Account created for ${user.firstName} ${user.lastName} (${user.email}).`,
                "success"
            );
        } catch (error) {
            setMessage(message, error.message, "error");
        }
    });
}

function renderMovieTable(movies) {
    const body = document.querySelector("#movie-table-body");
    if (!body) {
        return;
    }

    if (!movies.length) {
        body.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">No movies have been added yet.</td>
            </tr>
        `;
        return;
    }

    body.innerHTML = movies
        .map((movie) => `
            <tr>
                <td>${escapeHtml(movie.title)}</td>
                <td>${movie.inStock}</td>
                <td>${movie.checkedOut}</td>
                <td>
                    <button class="secondary-button" type="button" data-action="add" data-movie-id="${movie.id}">+</button>
                </td>
                <td>
                    <button class="secondary-button danger" type="button" data-action="remove" data-movie-id="${movie.id}">-</button>
                </td>
            </tr>
        `)
        .join("");
}

function initMoviePage() {
    const form = document.querySelector("#movie-form");
    const message = document.querySelector("#movie-message");
    const tableBody = document.querySelector("#movie-table-body");
    if (!form || !message || !tableBody) {
        return;
    }

    async function loadMovies() {
        try {
            const movies = await requestJson("/dbMovie/");
            renderMovieTable(movies);
        } catch (error) {
            setMessage(message, error.message, "error");
            renderMovieTable([]);
        }
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        setMessage(message, "");

        try {
            const movies = await requestJson("/dbMovie/", {
                method: "POST",
                body: {
                    action: "new",
                    title: form.title.value
                }
            });
            form.reset();
            renderMovieTable(movies);
            setMessage(message, "Movie added to inventory.", "success");
        } catch (error) {
            setMessage(message, error.message, "error");
        }
    });

    tableBody.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) {
            return;
        }

        setMessage(message, "");

        try {
            const movies = await requestJson("/dbMovie/", {
                method: "POST",
                body: {
                    action: button.dataset.action,
                    movieId: button.dataset.movieId
                }
            });
            renderMovieTable(movies);
        } catch (error) {
            setMessage(message, error.message, "error");
        }
    });

    loadMovies();
}

function initRentPage() {
    const form = document.querySelector("#member-search-form");
    const message = document.querySelector("#rent-message");
    const memberResults = document.querySelector("#member-results");
    const memberName = document.querySelector("#member-name");
    const memberEmail = document.querySelector("#member-email-display");
    const checkedOutBody = document.querySelector("#checked-out-body");
    const availableMoviesBody = document.querySelector("#available-movies-body");
    if (
        !form ||
        !message ||
        !memberResults ||
        !memberName ||
        !memberEmail ||
        !checkedOutBody ||
        !availableMoviesBody
    ) {
        return;
    }

    const state = {
        user: null,
        checkouts: [],
        movies: []
    };

    function clearMemberView() {
        state.user = null;
        state.checkouts = [];
        state.movies = [];
        memberResults.classList.add("hidden");
        checkedOutBody.innerHTML = `
            <tr>
                <td colspan="2" class="empty-state">Search for a member to view rentals.</td>
            </tr>
        `;
        availableMoviesBody.innerHTML = `
            <tr>
                <td colspan="3" class="empty-state">Available movies appear after a member lookup.</td>
            </tr>
        `;
    }

    function rentableMovies() {
        const rentedMovieIds = new Set(state.checkouts.map((checkout) => checkout.movieId));
        return state.movies.filter((movie) => movie.available > 0 && !rentedMovieIds.has(movie.id));
    }

    function renderMemberView() {
        if (!state.user) {
            clearMemberView();
            return;
        }

        memberResults.classList.remove("hidden");
        memberName.textContent = `${state.user.firstName} ${state.user.lastName}`;
        memberEmail.textContent = state.user.email;

        if (state.checkouts.length) {
            checkedOutBody.innerHTML = state.checkouts
                .map((checkout) => `
                    <tr>
                        <td>${escapeHtml(checkout.title)}</td>
                        <td>
                            <button class="secondary-button danger" type="button" data-action="return" data-movie-id="${checkout.movieId}">
                                Return
                            </button>
                        </td>
                    </tr>
                `)
                .join("");
        } else {
            checkedOutBody.innerHTML = `
                <tr>
                    <td colspan="2" class="empty-state">This member has no movies checked out.</td>
                </tr>
            `;
        }

        const available = rentableMovies();
        if (available.length) {
            availableMoviesBody.innerHTML = available
                .map((movie) => `
                    <tr>
                        <td>${escapeHtml(movie.title)}</td>
                        <td>${movie.available}</td>
                        <td>
                            <button class="secondary-button" type="button" data-action="rent" data-movie-id="${movie.id}">
                                Rent
                            </button>
                        </td>
                    </tr>
                `)
                .join("");
        } else {
            availableMoviesBody.innerHTML = `
                <tr>
                    <td colspan="3" class="empty-state">No movies are currently available for this member.</td>
                </tr>
            `;
        }
    }

    async function refreshMemberData() {
        if (!state.user) {
            return;
        }

        const [checkouts, movies] = await Promise.all([
            requestJson(`/dbRent/?userId=${encodeURIComponent(state.user.id)}`),
            requestJson("/dbMovie/")
        ]);

        state.checkouts = checkouts;
        state.movies = movies;
        renderMemberView();
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        setMessage(message, "");

        try {
            const user = await requestJson(`/dbUser/?email=${encodeURIComponent(form.email.value)}`);
            state.user = user;
            await refreshMemberData();
            setMessage(message, `Loaded rental profile for ${user.firstName} ${user.lastName}.`, "success");
        } catch (error) {
            clearMemberView();
            setMessage(message, error.message, "error");
        }
    });

    async function handleAction(movieId, action) {
        if (!state.user) {
            setMessage(message, "Load a member before renting or returning movies.", "error");
            return;
        }

        setMessage(message, "");

        try {
            const [checkouts, movies] = await Promise.all([
                requestJson("/dbRent/", {
                    method: "POST",
                    body: {
                        userId: state.user.id,
                        movieId,
                        action
                    }
                }),
                requestJson("/dbMovie/")
            ]);
            state.checkouts = checkouts;
            state.movies = movies;
            renderMemberView();
            setMessage(
                message,
                action === "rent" ? "Movie rented successfully." : "Movie returned successfully.",
                "success"
            );
        } catch (error) {
            setMessage(message, error.message, "error");
        }
    }

    checkedOutBody.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action='return']");
        if (!button) {
            return;
        }
        await handleAction(button.dataset.movieId, "return");
    });

    availableMoviesBody.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action='rent']");
        if (!button) {
            return;
        }
        await handleAction(button.dataset.movieId, "rent");
    });

    clearMemberView();
}

if (page === "account") {
    initAccountPage();
}

if (page === "movie") {
    initMoviePage();
}

if (page === "rent") {
    initRentPage();
}
